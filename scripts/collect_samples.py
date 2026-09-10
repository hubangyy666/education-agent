"""Collect a bounded COCO training reserve with official ground truth and provenance."""
from pathlib import Path
import json
import urllib.request
import zipfile
import sys
from concurrent.futures import ThreadPoolExecutor

root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from backend.grading import polygon_metrics
limit=int(sys.argv[1]) if len(sys.argv)>1 else 120
downloads = root / 'data' / 'downloads'
downloads.mkdir(parents=True, exist_ok=True)
out = root / 'data' / 'samples'
out.mkdir(parents=True, exist_ok=True)
archive = downloads / 'annotations_trainval2017.zip'
if not archive.exists():
    print('正在获取 COCO 官方标注与许可元数据…', flush=True)
    urllib.request.urlretrieve('https://s3.amazonaws.com/images.cocodataset.org/annotations/annotations_trainval2017.zip', archive)
with zipfile.ZipFile(archive) as z:
    dataset = json.loads(z.read('annotations/instances_val2017.json'))
categories = {c['id']:c['name'] for c in dataset['categories']}
licenses = {c['id']:c for c in dataset['licenses']}
annotations = {}
for a in dataset['annotations']:
    if not a['iscrowd'] and isinstance(a['segmentation'], list):
        annotations.setdefault(a['image_id'], []).append(a)
names = {'cat':'猫','dog':'狗','person':'行人','car':'汽车','bus':'公交车','bicycle':'自行车','motorcycle':'摩托车','truck':'卡车','bird':'鸟','horse':'马','chair':'椅子','cup':'杯子'}
selected = []
for im in sorted(dataset['images'], key=lambda im: (im['id'] != 39769, im['id'])):
    # Only reusable CC BY / BY-SA images. Preserve every per-image source.
    if im['license'] not in (4, 5):
        continue
    targets = [a for a in annotations.get(im['id'], []) if categories[a['category_id']] in names and a['area']/(im['width']*im['height']) >= .002]
    if targets and max(a['area']/(im['width']*im['height']) for a in targets)>.04 and (len(selected) < limit):
        selected.append((im,targets))
def download(item):
    im, targets = item
    path = out / im['file_name']
    if not path.exists():
        urllib.request.urlretrieve(im['coco_url'].replace('http://images.cocodataset.org/', 'https://s3.amazonaws.com/images.cocodataset.org/'), path)
    record = {'id':str(im['id']), 'file':im['file_name'], 'width':im['width'], 'height':im['height'], 'source_url':im['flickr_url'], 'dataset_url':'https://cocodataset.org/#download', 'license':licenses[im['license']], 'targets':[]}
    for a in targets:
        x,y,w,h = a['bbox']
        poly = max(a['segmentation'], key=len)
        polygon=[[poly[j]/im['width'],poly[j+1]/im['height']] for j in range(0,len(poly),2)]
        record['targets'].append({'label':names[categories[a['category_id']]], 'box':[x/im['width'],y/im['height'],w/im['width'],h/im['height']], 'polygon':polygon,'polygon_valid':polygon_metrics(polygon,polygon)[0]>.99, 'area_ratio':a['area']/(im['width']*im['height']), 'annotation_id':a['id']})
    return record
with ThreadPoolExecutor(max_workers=6) as pool:
    records = list(pool.map(download,selected))
(out / 'manifest.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'已保存 {len(records)} 个真实图像及官方标注，附来源与许可。', flush=True)
