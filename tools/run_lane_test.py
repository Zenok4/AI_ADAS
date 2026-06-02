import os
import sys
import cv2
import numpy as np

# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.lane_service import lane_prediction
from app.services.lane_context_service import analyze_current_lane
from app.config.settings import settings

os.makedirs('debug_frames/test_output', exist_ok=True)

images = [
    'debug_frames/lane/160857_627851.jpg',
    'debug_frames/lane/162240_358683.jpg',
]

results = []
for path in images:
    img = cv2.imread(path)
    if img is None:
        print('ERR load', path)
        continue
    dets = lane_prediction(img)
    current = analyze_current_lane(dets, img.shape, drift_threshold=settings.LANE_DEPARTURE['offset_threshold'])

    # draw detections
    overlay = img.copy()
    for d in dets:
        box = d.get('box', [])
        if len(box) == 4:
            x1,y1,x2,y2 = map(int, box)
            color = (0,255,255) if d.get('class_name','')=='left_lane' else (255,0,255)
            cv2.rectangle(overlay, (x1,y1),(x2,y2), color, 2)
            cv2.putText(overlay, f"{d.get('class_name','')}: {d.get('confidence',0):.2f}", (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # draw lane center
    if current.get('available'):
        lcx = int(current.get('lane_center_x',0))
        cv2.line(overlay, (lcx,0),(lcx,img.shape[0]), (0,255,0),2)
        cv2.putText(overlay, f"offset_ratio: {current.get('offset_ratio',0):.3f}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0),2)
    else:
        cv2.putText(overlay, 'No lane available', (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255),2)

    outp = path.replace('debug_frames/lane/','debug_frames/test_output/annot_')
    cv2.imwrite(outp, overlay)

    results.append({'image': path, 'detections': dets, 'current_lane': current, 'output': outp})

for r in results:
    print('---', r['image'])
    print('detections:')
    for d in r['detections']:
        print('-', d.get('class_name'), d.get('line'), 'conf', d.get('confidence'))
    print('current_lane:', {k: r['current_lane'].get(k) for k in ('available','status','offset_ratio','lane_center_x','lane_width_px')})
    print('saved:', r['output'])
