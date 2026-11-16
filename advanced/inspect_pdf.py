"""Inspect every IPCC page, native text/layout, tables and visual-reference pages."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / 'data/IPCC_AR6_SYR_FullVolume.pdf'
OUT = ROOT / 'advanced/artifacts/document'
CAPTION = re.compile(r'^(Figure|Table)\s+((?:SPM\.)?\d+(?:\.\d+)?)\s*[:|.]?\s', re.I)
BOX_CAPTION = re.compile(r'((?:Cross-Section\s+)?Box\.?\s*(?:SPM\.)?\d+)[,\s]+(Figure|Table)\s+(\d+)\s*:', re.I)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def inspect(source=PDF, output=OUT):
    import pymupdf
    doc = pymupdf.open(source)
    pages = []
    visuals = []
    for index, page in enumerate(doc):
        number = index+1
        text = page.get_text('text', sort=True)
        words = page.get_text('words', sort=True)
        blocks = []
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:
                continue
            content = '\n'.join(''.join(s['text'] for s in line['spans']) for line in block['lines'])
            if content.strip():
                blocks.append({'bbox':list(block['bbox']), 'text':content})
        captions = []
        for b in blocks:
            for line in b['text'].splitlines():
                nested = BOX_CAPTION.search(line.strip())
                if nested:
                    box = re.sub(r'Cross-Section\s+', '', nested[1], flags=re.I)
                    box = re.sub(r'Box\.?\s*', 'Box ', box, flags=re.I)
                    captions.append({'label':f'{box} {nested[2].title()} {nested[3]}',
                                     'bbox':b['bbox'],'text':b['text']})
                match = CAPTION.match(line.strip())
                if match:
                    label = f'{match[1].title()} {match[2]}'
                    captions.append({'label':label, 'bbox':b['bbox'], 'text':b['text']})
        tables = []
        if len(page.get_drawings()) >= 15:
            found = page.find_tables()
            for i,t in enumerate(found.tables):
                rows = t.extract()
                if len(rows)>=2 and max(len(row) for row in rows)>=2:
                    tables.append({'table_index':i, 'bbox':list(t.bbox),'rows':rows})
        images = page.get_images(full=True)
        info = {'page':number,'printed_label':page.get_label(), 'width':page.rect.width,
                'height':page.rect.height,'text':text,'blocks':blocks,
                'words':[list(w[:5]) for w in words],'captions':captions,'tables':tables,
                'image_count':len(images), 'drawing_count':len(page.get_drawings()),
                'status':'indexed_text_layout' if text.strip() else 'empty_or_image_only'}
        if captions:
            info['page_image'] = f'advanced/artifacts/document/pages/page-{number:03}.png'
            target = output / 'pages' / f'page-{number:03}.png'
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                page.get_pixmap(dpi=110,alpha=False).save(target)
            for caption in captions:
                visuals.append({'page':number, **caption, 'page_image':info['page_image'],
                                'page_bbox':[0,0,page.rect.width,page.rect.height]})
        pages.append(info)
    dump(output/'pages.json',pages)
    dump(output/'visuals.json',visuals)
    manifest={'title':'Climate Change 2023: Synthesis Report. IPCC AR6',
        'source_path':str(source.relative_to(ROOT)).replace('\\','/'),
        'source_url':'https://www.ipcc.ch/report/ar6/syr/downloads/report/IPCC_AR6_SYR_FullVolume.pdf',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'physical_pages':len(pages),'text_pages':sum(bool(p['text'].strip()) for p in pages),
        'visual_reference_pages':sorted({v['page'] for v in visuals}),
        'captions_detected':len(visuals),'tables_extracted':sum(len(p['tables']) for p in pages),
        'page_status_counts':dict(Counter(p['status'] for p in pages)),
        'copyright':'IPCC 2023. PDF physical page 4 permits attributed short extracts; full publication rights reserved. Source PDF and derived full-text/image assets are local-only and git-ignored.',
        'scope':'All 186 physical pages inspected. Text and native spatial labels are extracted; figures have rendered page images and bboxes. Decorative/blank pages are reported, not padded.'}
    dump(output/'manifest.json',manifest)
    print(json.dumps(manifest,ensure_ascii=False,indent=2),flush=True)
    return pages,visuals


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=PDF)
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args()
    inspect(args.source,args.output)


if __name__=='__main__':
    main()
