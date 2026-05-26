# ============================================================
#  FILE: edge/yolo_ocr.py
#  OCR: EasyOCR with Kerala plate format validation
#  Kerala plate format: KL-DD-[A/AA]-NNNN
#    KL       = state code (always)
#    DD       = 2 digit district number (01-75)
#    A or AA  = 1 or 2 alphabets (series, no I or O)
#    NNNN     = 4 digits
# ============================================================

import cv2
import numpy as np
import datetime
import json
import os
import re
import time
import easyocr
from collections import Counter
from ultralytics import YOLO
import logging
logging.disable(logging.CRITICAL)
import queue
import argparse

# ── Connect to MongoDB at startup ─────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from cont_database import connect, save_detection
connect()

# ── Streaming mode setup ──────────────────────────────────────
frame_queue = queue.Queue(maxsize=2)
streaming_mode = False

# ──────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────
VIDEO_SOURCE     = "test_video1.MOV"   # overridden by argparse at runtime
BUS_NUMBERS_FILE = os.path.join(os.path.dirname(__file__), 'test_video1.MOV').replace('test_video1.MOV','') 
BUS_NUMBERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'config', 'bus_numbers.txt')
BUS_MODEL        = "models/yolo12n.pt"
PLATE_MODEL      = "models/license_plate_detector.pt"
TRIPWIRE_RATIO   = 0.5
BUS_CONF         = 0.25
PLATE_CONF       = 0.35
BUS_CLASS_ID     = 5
OUTPUT_LOG   = os.path.join(os.path.dirname(__file__), '..', 'data', 'detection_log.json')
OUTPUT_VIDEO = os.path.join(os.path.dirname(__file__), '..', 'data', 'detection_output.avi')
PLATE_BOX_FRAMES = 45

# ── Speed tuning ───────────────────────────────────────────────
# EasyOCR takes ~1-2 sec per call — running it every frame causes
# slow motion. OCR_INTERVAL=5 means OCR runs once per 5 frames.
# At 25fps this gives 5 OCR reads/sec — plenty for a gate crossing bus.
# Increase to 8 or 10 if video is still slow on your hardware.
OCR_INTERVAL = 5
SHOW_WINDOW  = False    # True = show live video window

# ──────────────────────────────────────────────────────────────
# KERALA PLATE FORMAT VALIDATOR & CORRECTOR
# ──────────────────────────────────────────────────────────────

KERALA_DISTRICTS     = {str(i).zfill(2) for i in range(1, 76)}
VALID_SERIES_LETTERS = set('ABCDEFGHJKLMNPQRSTUVWXYZ')  # no I, no O

KERALA_PLATE_PATTERN = re.compile(
    r'KL(\d{2})([A-HJ-NP-Z]{1,2})(\d{4})'
)

def clean_ocr_text(text):
    return ''.join(c for c in text.upper() if c.isalnum())

def fix_common_ocr_errors(text):
    text = text.upper().strip()
    text = re.sub(r'[\s\.\-_]', '', text)
    text = re.sub(r'^K[LI1|]', 'KL', text)
    text = re.sub(r'^[KX][LI1]', 'KL', text)
    return text

def validate_kerala_plate(text):
    text = fix_common_ocr_errors(text)
    if len(text) < 9 or len(text) > 10:
        return None
    if not text.startswith('KL'):
        return None
    after_kl = text[2:]
    if not after_kl[:2].isdigit():
        return None
    district = after_kl[:2]
    if district not in KERALA_DISTRICTS:
        return None
    after_district = after_kl[2:]
    if len(after_district) == 6:
        series = after_district[:2]
        number = after_district[2:]
        if all(c in VALID_SERIES_LETTERS for c in series) and number.isdigit():
            return f"KL{district}{series}{number}"
    if len(after_district) == 5:
        series = after_district[:1]
        number = after_district[1:]
        if series in VALID_SERIES_LETTERS and number.isdigit():
            return f"KL{district}{series}{number}"
    return None

def try_fix_partial_plate(text):
    text = fix_common_ocr_errors(text)
    if len(text) < 8:
        return None
    if not text.startswith('KL'):
        if text.startswith('K') and len(text) >= 9:
            text = 'KL' + text[2:]
        else:
            return None
    result = list(text)
    result[0] = 'K'
    result[1] = 'L'
    digit_fixes  = {'O':'0','I':'1','L':'1','Z':'2','S':'5',
                    'G':'6','T':'7','B':'8','A':'4','E':'3'}
    letter_fixes = {'0':'D','1':'J','2':'Z','4':'A',
                    '3':'E','5':'S','6':'G','8':'B'}
    for i in [2, 3]:
        if i < len(result) and not result[i].isdigit():
            result[i] = digit_fixes.get(result[i], result[i])
    if len(result) >= 9:
        for i in range(len(result)-4, len(result)):
            if not result[i].isdigit():
                result[i] = digit_fixes.get(result[i], result[i])
        for i in range(4, len(result)-4):
            if result[i].isdigit():
                result[i] = letter_fixes.get(result[i], result[i])
    return validate_kerala_plate(''.join(result))

def merge_two_row_plate(ocr_results):
    """
    Two-row plates (e.g. KL48 / T 0617) appear as two separate
    EasyOCR fragments. Try all top+bottom ordered pairs and return
    the first combination that forms a valid Kerala plate.
    ocr_results: list of (conf, text, cy)  — cy = vertical centre
    """
    sorted_r = sorted(ocr_results, key=lambda x: x[2])  # top row first
    texts = [(''.join(c for c in t.upper() if c.isalnum()), conf)
             for conf, t, cy in sorted_r]
    for i in range(len(texts)):
        for j in range(len(texts)):
            if i == j:
                continue
            combined = texts[i][0] + texts[j][0]
            valid = validate_kerala_plate(combined)
            if valid:
                avg_conf = (texts[i][1] + texts[j][1]) / 2
                print(f"    [MERGE] '{texts[i][0]}' + '{texts[j][0]}'"
                      f" → '{valid}' conf={avg_conf:.2f}")
                return valid, avg_conf
    return None, 0.0

def extract_best_plate(ocr_results):
    """
    3-stage extraction:
      1. Direct Kerala validation on each fragment
      2. Auto-correction (position-based character fixes)
      3. Two-row merge (combine top+bottom row fragments)
    ocr_results: list of (conf, text, cy)
    """
    best_plate = "UNKNOWN"
    best_conf  = 0.0

    for conf, raw_text, cy in ocr_results:
        cleaned = clean_ocr_text(raw_text)
        valid   = validate_kerala_plate(cleaned)
        if valid:
            print(f"    [OK]    '{valid}' from '{raw_text}' conf={conf:.2f}")
            if conf > best_conf:
                best_conf, best_plate = conf, valid
            continue
        fixed = try_fix_partial_plate(cleaned)
        if fixed:
            print(f"    [FIXED] '{fixed}' from '{raw_text}' conf={conf:.2f}")
            if conf > best_conf * 0.9:
                best_conf, best_plate = conf, fixed
            continue
        print(f"    [SKIP]  '{cleaned}' conf={conf:.2f}")

    if best_plate == "UNKNOWN" and len(ocr_results) >= 2:
        merged, mconf = merge_two_row_plate(ocr_results)
        if merged:
            best_plate, best_conf = merged, mconf

    return best_plate, best_conf

# ──────────────────────────────────────────────────────────────
# LOAD BUS NUMBERS
# ──────────────────────────────────────────────────────────────
def load_bus_numbers(filepath):
    if not os.path.exists(filepath):
        print(f"[WARNING] {filepath} not found.")
        return []
    with open(filepath, "r") as f:
        raw = [line.strip().upper() for line in f if line.strip()]
    cleaned, seen = [], set()
    for num in raw:
        v = validate_kerala_plate(clean_ocr_text(num))
        if v and v not in seen:
            cleaned.append(v)
            seen.add(v)
    print(f"[INFO] Loaded {len(cleaned)} buses: {cleaned}")
    return cleaned

# ──────────────────────────────────────────────────────────────
# OCR ENGINE — initialised once at import time
# ──────────────────────────────────────────────────────────────
print("[INFO] Initialising EasyOCR ...")
ocr_engine = easyocr.Reader(['en'], gpu=False, verbose=False)
print("[INFO] EasyOCR ready")

def preprocess_plate(img):
    """Upscale → sharpen → CLAHE contrast enhancement."""
    h, w = img.shape[:2]
    if h < 5 or w < 5:
        return img
    scale = max(3, int(200 / max(h, 1)))
    img   = cv2.resize(img, (w*scale, h*scale), interpolation=cv2.INTER_LANCZOS4)
    img   = cv2.filter2D(img, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]]))
    lab   = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l,a,b = cv2.split(lab)
    l     = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4)).apply(l)
    return cv2.cvtColor(cv2.merge([l,a,b]), cv2.COLOR_LAB2BGR)

def run_easyocr(img):
    """Return list of (conf, text, cy). cy = vertical centre of bbox."""
    results = []
    try:
        for (bbox, text, conf) in ocr_engine.readtext(
                img, detail=1,
                allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
            cleaned = ''.join(c for c in text.upper() if c.isalnum())
            # 2-12 chars keeps short fragments (KL48, T0617) and full plates
            # rejects long bus-body text (>12 chars like EDUCATIONALINSTBUS)
            if 2 <= len(cleaned) <= 12:
                cy = int((bbox[0][1] + bbox[2][1]) / 2)
                results.append((conf, text.strip(), cy))
    except Exception as e:
        print(f"[OCR ERROR] {e}")
    return results

def read_plate(plate_crop):
    """
    Run OCR on 2 preprocessed versions only (grayscale + Otsu).
    Previously 4 versions — cutting to 2 halves OCR time with
    no meaningful accuracy loss for Kerala plates.
    """
    if plate_crop is None or plate_crop.size == 0:
        return "UNKNOWN", 0.0

    processed   = preprocess_plate(plate_crop)
    all_results = []

    # Version 1: Grayscale
    gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
    all_results.extend(run_easyocr(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)))

    # Version 2: Otsu threshold — high contrast, best for white plates
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    all_results.extend(run_easyocr(cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)))

    # Deduplicate — keep highest conf per cleaned text, preserve cy
    seen = {}
    for conf, text, cy in all_results:
        c = clean_ocr_text(text)
        if c not in seen or conf > seen[c][0]:
            seen[c] = (conf, text, cy)

    deduped = sorted(seen.values(), reverse=True)
    print(f"  OCR [{len(deduped)} fragments]: "
          f"{[(t, f'{c:.2f}') for c,t,_ in deduped[:6]]}")
    return extract_best_plate(deduped)

# ──────────────────────────────────────────────────────────────
# MATCH AGAINST OFFICIAL BUS LIST
# ──────────────────────────────────────────────────────────────
def match_bus_number(detected, official_list):
    if not official_list:
        return detected if detected != "UNKNOWN" else None
    d  = clean_ocr_text(detected)
    dv = validate_kerala_plate(d) or d
    for official in official_list:
        o = clean_ocr_text(official)
        if dv == o:
            return official
        if len(dv) == len(o):
            diffs = sum(1 for a,b in zip(dv,o) if a != b)
            if diffs <= 1:
                print(f"  [FUZZY] '{dv}' ≈ '{o}' ({diffs} diff)")
                return official
    return None

# ──────────────────────────────────────────────────────────────
# TRIPWIRE
# ──────────────────────────────────────────────────────────────
bus_prev_x = {}
bus_logged  = {}

def check_tripwire(tid, cx, tx):
    if tid not in bus_prev_x:
        bus_prev_x[tid] = cx
        return None
    prev = bus_prev_x[tid]
    bus_prev_x[tid] = cx
    if prev > tx >= cx:
        return "ENTRY"
    if prev < tx <= cx:
        return "EXIT"
    return None

# ──────────────────────────────────────────────────────────────
# SAVE LOG
# ──────────────────────────────────────────────────────────────
def save_log(bus_number, direction, timestamp):
    entry = {
        "bus_number": bus_number,
        "direction":  direction,
        "date":       timestamp.split(" ")[0],
        "time":       timestamp.split(" ")[1],
        "timestamp":  timestamp,
        "status":     "pending"
    }
    logs = []
    if os.path.exists(OUTPUT_LOG):
        with open(OUTPUT_LOG, "r") as f:
            try:    logs = json.load(f)
            except: logs = []
    logs.append(entry)
    with open(OUTPUT_LOG, "w") as f:
        json.dump(logs, f, indent=2)

    doc_id = save_detection(bus_number, direction, timestamp)
    entry["status"]    = "synced" if doc_id else "failed"
    logs[-1]["status"] = entry["status"]
    with open(OUTPUT_LOG, "w") as f:
        json.dump(logs, f, indent=2)

    db_status = f"synced (ID: {doc_id})" if doc_id else "failed — local backup only"
    print("\n" + "="*55)
    print("  BUS LOGGED")
    print(f"  Plate     : {bus_number}")
    print(f"  Direction : {direction}")
    print(f"  Date      : {entry['date']}")
    print(f"  Time      : {entry['time']}")
    print(f"  DB Status : {db_status}")
    print("="*55 + "\n")
    # notify backend that detection happened (for socket.io push)
    try:
        import requests
        requests.post("http://localhost:5000/api/detection/notify", 
                      json={"bus_number": bus_number, "direction": direction,
                            "timestamp": timestamp}, timeout=2)
    except:
        pass

# ──────────────────────────────────────────────────────────────
# MAIN DETECTION LOOP
# ──────────────────────────────────────────────────────────────
def run_detection():
    print("[INFO] Loading Bus model ...")
    bus_model = YOLO(BUS_MODEL)

    if not os.path.exists(PLATE_MODEL):
        print(f"[ERROR] {PLATE_MODEL} not found!")
        return
    print("[INFO] Loading Plate model ...")
    plate_model = YOLO(PLATE_MODEL)
    print("[INFO] Both models loaded\n")

    official_buses = load_bus_numbers(BUS_NUMBERS_FILE)

    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open {VIDEO_SOURCE}")
        return

    W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    FPS = int(cap.get(cv2.CAP_PROP_FPS)) or 25
    TX  = int(W * TRIPWIRE_RATIO)

    print(f"[INFO] Resolution  : {W}x{H} @ {FPS}fps")
    print(f"[INFO] Tripwire X  : {TX}px")
    print(f"[INFO] OCR every   : {OCR_INTERVAL} frames  "
          f"(~{FPS//OCR_INTERVAL} reads/sec)")
    print(f"[INFO] Show window : {SHOW_WINDOW}")
    print("[INFO] Press Q to quit\n")

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    writer = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS, (W, H))

    frame_count      = 0
    buses_detected   = 0
    plate_boxes      = {}
    plate_candidates = {}   # tid -> [(plate_text, conf), ...]
    bus_direction    = {}   # tid -> "ENTRY" / "EXIT"

    # Target ms per frame for real-speed display
    frame_ms = max(1, int(1000 / FPS))

    while True:
        t0 = time.time()

        ret, frame = cap.read()
        if not ret:
            print(f"\n[INFO] Video ended.")
            print(f"[INFO] Frames processed : {frame_count}")
            print(f"[INFO] Buses logged     : {buses_detected}")
            break

        frame_count += 1

        # ── Plate detector — every frame (fast) ───────────────────
        plate_res = plate_model(frame, conf=PLATE_CONF, verbose=False)
        current_plates = []
        if plate_res[0].boxes is not None and len(plate_res[0].boxes) > 0:
            for pb in plate_res[0].boxes:
                px1,py1,px2,py2 = map(int, pb.xyxy.cpu().numpy()[0])
                current_plates.append((px1,py1,px2,py2, float(pb.conf)))

        # ── Bus detector + tracker — every frame ──────────────────
        bus_res = bus_model.track(frame, persist=True,
                                  classes=[BUS_CLASS_ID],
                                  conf=BUS_CONF, verbose=False)

        # Draw tripwire
        cv2.line(frame, (TX,0),(TX,H), (0,255,255), 2)
        cv2.putText(frame, "TRIPWIRE", (TX+5,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

        # Timestamp
        ts = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        cv2.putText(frame, ts, (10,H-15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)

        if bus_res[0].boxes is not None and bus_res[0].boxes.id is not None:
            boxes = bus_res[0].boxes.xyxy.cpu().numpy()
            tids  = bus_res[0].boxes.id.cpu().numpy().astype(int)
            confs = bus_res[0].boxes.conf.cpu().numpy()

            for box, tid, conf in zip(boxes, tids, confs):
                x1,y1,x2,y2 = map(int, box)
                cx = (x1 + x2) // 2

                direction = check_tripwire(tid, cx, TX)

                cv2.rectangle(frame, (x1,y1),(x2,y2), (0,200,0), 2)
                cv2.putText(frame, f"BUS #{tid}  {conf:.2f}",
                            (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0,200,0), 2)

                # Record direction once at tripwire crossing
                if direction and tid not in bus_direction:
                    bus_direction[tid] = direction
                    print(f"\n[TRIPWIRE] Bus #{tid} → {direction} "
                          f"(frame {frame_count})")

                # ── OCR only every OCR_INTERVAL frames ────────────
                # KEY FIX: skipping frames keeps video at real speed.
                # The bus is in frame for many frames so we still
                # collect multiple plate readings per bus.
                if tid not in bus_logged and (frame_count % OCR_INTERVAL == 0):

                    best_plate, best_pc = None, 0.0
                    for (px1,py1,px2,py2,pc) in current_plates:
                        in_x = x1-30 <= px1 and px2 <= x2+30
                        in_y = y1-30 <= py1 and py2 <= y2+30
                        if in_x and in_y and pc > best_pc:
                            best_pc, best_plate = pc, (px1,py1,px2,py2)

                    if best_plate is None and current_plates:
                        best = max(current_plates, key=lambda p: p[4])
                        best_plate, best_pc = best[:4], best[4]

                    if best_plate is not None:
                        px1,py1,px2,py2 = best_plate
                        pw, ph = px2-px1, py2-py1
                        if pw >= 60 and ph >= 15:
                            pad = 5
                            crop = frame[max(0,py1-pad):py2+pad,
                                         max(0,px1-pad):px2+pad]
                            plate_text, ocr_conf = read_plate(crop)

                            if plate_text != "UNKNOWN":
                                plate_candidates.setdefault(tid,[]).append(
                                    (plate_text, ocr_conf))
                                n = len(plate_candidates[tid])
                                print(f"  [CANDIDATE #{n}] Bus #{tid} "
                                      f"'{plate_text}' conf={ocr_conf:.2f}")

                            plate_boxes[tid] = [px1,py1,px2,py2,
                                                plate_text, PLATE_BOX_FRAMES]

                # ── Commit: direction known + enough candidates ────
                # Wait for >= 2 candidates so voting has real data.
                # bus_logged only set True on confirmed match —
                # a NO MATCH bus keeps collecting and retries next frame.
                if (tid in bus_direction
                        and tid not in bus_logged
                        and tid in plate_candidates
                        and len(plate_candidates[tid]) >= 2):

                    counts    = Counter(t for t,c in plate_candidates[tid])
                    best_text = max(counts, key=lambda t: (
                        counts[t],
                        max(c for txt,c in plate_candidates[tid] if txt==t)
                    ))
                    best_conf = max(c for txt,c in plate_candidates[tid]
                                    if txt==best_text)
                    matched   = match_bus_number(best_text, official_buses)
                    now_ts    = datetime.datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S")
                    final_dir = bus_direction[tid]

                    print(f"\n[COMMIT] Bus #{tid} | '{best_text}' "
                          f"x{counts[best_text]} conf={best_conf:.2f} "
                          f"dir={final_dir} | "
                          f"total={len(plate_candidates[tid])}")

                    if matched:
                        bus_logged[tid] = True  # lock only on real match
                        save_log(matched, final_dir, now_ts)
                        buses_detected += 1
                        cv2.putText(frame, f"MATCH: {matched} | {final_dir}",
                                    (x1,y2+35), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8, (0,255,0), 2)
                        cv2.rectangle(frame,(x1-4,y1-4),(x2+4,y2+4),
                                      (0,255,0), 3)
                    else:
                        # Keep collecting — better reading may arrive next frame
                        print(f"  [RETRY] '{best_text}' no match — "
                              f"collecting more candidates...")

        # Blue boxes on detected plates
        for (px1,py1,px2,py2,pc) in current_plates:
            cv2.rectangle(frame,(px1,py1),(px2,py2),(255,0,0),2)
            cv2.putText(frame, f"PLATE {pc:.2f}", (px1,py1-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 2)

        # Persistent plate label box countdown
        to_del = []
        for t_id, info in plate_boxes.items():
            px1,py1,px2,py2,ptxt,fl = info
            if fl > 0:
                cv2.rectangle(frame,(px1,py1),(px2,py2),(255,0,0),3)
                cv2.putText(frame, ptxt, (px1,py1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)
                plate_boxes[t_id][5] -= 1
            else:
                to_del.append(t_id)
        for t_id in to_del:
            del plate_boxes[t_id]

        writer.write(frame)

        # Real-speed playback: wait only the remaining frame time
        elapsed_ms = int((time.time() - t0) * 1000)
        wait_ms    = max(1, frame_ms - elapsed_ms)

        if streaming_mode:
            small = cv2.resize(frame, (480, 270))
            _, jpeg = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 40])
            data = jpeg.tobytes()
            import struct
            sys.stdout.buffer.write(struct.pack('>I', len(data)))
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        else:
            cv2.imshow("Campus Fleet Detection", frame)
            if cv2.waitKey(wait_ms) & 0xFF == ord('q'):
                break

    cap.release()
    writer.release()
    if not streaming_mode:
        cv2.destroyAllWindows()
    print(f"[INFO] Output saved : {OUTPUT_VIDEO}")
    # signal stream ended
    try:
        frame_queue.put_nowait(None)   # None = sentinel, stream is finished
    except:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=str, default=VIDEO_SOURCE,
                        help='video file to process')
    parser.add_argument('--stream', action='store_true',
                        help='enable MJPEG streaming mode (no cv2.imshow)')
    args = parser.parse_args()

    VIDEO_SOURCE   = args.video
    streaming_mode = args.stream

    run_detection()