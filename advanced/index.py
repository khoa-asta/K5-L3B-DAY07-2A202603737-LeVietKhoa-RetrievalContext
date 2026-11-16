"""Index all native IPCC text, table grids and spatial figure labels; no gold input."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata

from advanced.inspect_pdf import PDF,OUT,dump

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'starter'))
ART=ROOT/'advanced/artifacts/index'


def clean(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text)).strip()


def table_text(table,label):
    rows=table['rows']
    lines=[f'{label}. Extracted spatial table; cell indexes are one-based. Blank cells are not invented.']
    for index,row in enumerate(rows,1):
        lines.append(f'Row {index}: '+' | '.join(f'C{col}: {clean(cell)}' for col,cell in enumerate(row,1) if cell))
    return '\n'.join(lines)


def spatial_lines(words):
    lines=[]
    current=[];y=None
    for word in sorted(words,key=lambda w:(round(w[1]/4),w[0])):
        if y is None or abs(word[1]-y)<4:
            current.append(word);y=word[1] if y is None else y
        else:
            lines.append(' '.join(w[4] for w in sorted(current,key=lambda w:w[0])))
            current=[word];y=word[1]
    if current:lines.append(' '.join(w[4] for w in sorted(current,key=lambda w:w[0])))
    return '\n'.join(clean(line) for line in lines if clean(line))


def make_units(pages,pdf_sha,page_numbers=None):
    units=[]
    for p in pages:
        if page_numbers is not None and p['page'] not in page_numbers:continue
        number=p['page']
        for bi,b in enumerate(p['blocks']):
            text=clean(b['text'])
            if len(text)<25:continue
            units.append({'id':f'ipcc-p{number:03}-b{bi:03}', 'kind':'text', 'page':number,
                          'bbox':b['bbox'],'text':text,'label':f'PDF page {number}',
                          'source_pages':[number]})
        for ti,t in enumerate(p['tables']):
            if sum(bool(c) for row in t['rows'] for c in row)<6:continue
            label=next((c['label'] for c in p['captions'] if 'Table' in c['label']),f'Layout table page {number}')
            units.append({'id':f'ipcc-p{number:03}-table{ti:02}', 'kind':'table','page':number,
                          'bbox':t['bbox'],'text':table_text(t,label),'rows':t['rows'],
                          'label':label,'source_pages':[number]})
    # Caption + immediately preceding graphical pages form one figure unit.
    for p in pages:
        if page_numbers is not None and p['page'] not in page_numbers:continue
        for ci,caption in enumerate(p['captions']):
            label=caption['label']
            if 'Figure' not in label:continue
            related=[p]
            for previous in reversed(pages[max(0,p['page']-4):p['page']-1]):
                if previous['captions'] or previous['drawing_count']<40:break
                related.insert(0,previous)
            primary=max(related,key=lambda row:row['drawing_count'])
            number=primary['page']
            text=f'{label}\n'+ '\n'.join(f'PDF page {page["page"]}, native spatial labels:\n'+spatial_lines(page['words']) for page in related)
            units.append({'id':f'ipcc-visual-{p["page"]:03}-{ci:02}','kind':'figure',
                'page':number,'bbox':[0,0,primary['width'],primary['height']],
                'text':text,'label':label,'source_pages':[page['page'] for page in related],
                'caption':clean(caption['text']), 'page_image':f'advanced/artifacts/document/pages/page-{number:03}.png',
                'representation':'Native vector labels, spatial ordering, caption, and rendered page; no inferred values from chart pixels.'})
    for unit in units:
        unit.update(source_id='ipcc_ar6_syr',source='data/IPCC_AR6_SYR_FullVolume.pdf',source_sha256=pdf_sha)
    return units


def split_unit(unit,tokenizer,budget=88,overlap=12):
    text=unit['text']
    enc=tokenizer(text,add_special_tokens=False,return_offsets_mapping=True,truncation=False,verbose=False)
    offsets=enc['offset_mapping']
    rows=[]
    for start in range(0,len(offsets),budget-overlap):
        batch=offsets[start:start+budget]
        if not batch:continue
        segment=text[batch[0][0]:batch[-1][1]]
        label=unit['label'] if unit['kind']!='text' else ''
        prefix=f'{label}. ' if label else ''
        emb_text=prefix+segment
        # A long figure label may consume more than the spare model capacity.
        while len(tokenizer(emb_text,add_special_tokens=True,truncation=False,verbose=False)['input_ids'])>126 and len(batch)>1:
            batch=batch[:-1];segment=text[batch[0][0]:batch[-1][1]];emb_text=prefix+segment
        cid=hashlib.sha256(f'{unit["source_sha256"]}:{unit["id"]}:{batch[0][0]}:{batch[-1][1]}'.encode()).hexdigest()[:24]
        rows.append({'id':cid,'unit_id':unit['id'],'text':emb_text,'source_id':unit['source_id'],
            'source':unit['source'],'page':unit['page'],'metadata':{'unit_id':unit['id'],
            'kind':unit['kind'],'label':unit['label'],'page':unit['page'],
            'bbox':json.dumps(unit['bbox']),'source_pages':json.dumps(unit['source_pages']),
            'source_sha256':unit['source_sha256']}})
        if start+budget>=len(offsets):break
    return rows


def coverage_report(pages,units):
    covered={number for u in units for number in u['source_pages']}
    return {'source_pages_covered':len(covered),'excluded_pages':[
        {'page':p['page'],'native_chars':len(clean(p['text'])),
         'reason':('No native text; raster-only content is not interpreted' if not clean(p['text']) else
                   'Only short native headings/labels/page numbers; no native text block reaches 25 characters; raster-only content is not interpreted')}
        for p in pages if p['page'] not in covered]}


def prepare(limit,max_seconds):
    from advanced.tokenizer_only import OfflineTokenizer
    from advanced.safety import atomic_json,guard,rest,stop_requested,memory_mb
    start=time.monotonic()
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    pages=json.loads((OUT/'pages.json').read_text(encoding='utf-8'))
    state_path=ART/'prepare-state.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {
        'next_page':1,'pdf_sha256':manifest['source_sha256'],'prepared_pages':0}
    if state['pdf_sha256']!=manifest['source_sha256']:raise ValueError('PDF changed; preserve old checkpoints and use a separate index directory.')
    if state['next_page']>len(pages) and (ART/'manifest.json').exists():
        saved=json.loads((ART/'manifest.json').read_text(encoding='utf-8'))
        saved.update(coverage_report(pages,json.loads((ART/'units.json').read_text(encoding='utf-8'))))
        atomic_json(ART/'manifest.json',saved)
        return {'stage':'prepare','pages_processed_this_run':0,'prepared_pages':len(pages),
                'total_pages':len(pages),'complete':True,'model_weights_loaded':False}
    tokenizer=OfflineTokenizer(ROOT/'starter/.models/paraphrase-multilingual-MiniLM-L12-v2/tokenizer.json')
    done=0
    while state['next_page']<=len(pages) and done<limit and time.monotonic()-start<max_seconds:
        if stop_requested():break
        guard();number=state['next_page']
        units=make_units(pages,manifest['source_sha256'],{number})
        chunks=[c for u in units for c in split_unit(u,tokenizer)]
        atomic_json(ART/'parts'/f'page-{number:03}.json',{'page':number,'units':units,'chunks':chunks})
        state.update(next_page=number+1,prepared_pages=number)
        atomic_json(state_path,state)
        done+=1;rest()
    if state['next_page']>len(pages):
        parts=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((ART/'parts').glob('page-*.json'))]
        if [part['page'] for part in parts]!=list(range(1,len(pages)+1)):
            raise ValueError('Page checkpoints are missing or duplicated; existing Chroma preserved.')
        body=[u for part in parts for u in part['units'] if u['kind']!='figure']
        figures=[u for part in parts for u in part['units'] if u['kind']=='figure']
        units=body+figures
        by_unit={}
        for part in parts:
            for c in part['chunks']:by_unit.setdefault(c['unit_id'],[]).append(c)
        chunks=[c for u in units for c in by_unit.get(u['id'],[])]
        signature=hashlib.sha256(json.dumps(chunks,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        # Refuse a tokenizer/corpus mismatch instead of silently creating another
        # collection and abandoning the vectors from before the interruption.
        stored=status().get('stored_collections',[])
        if stored and any(name!='ipcc_'+signature[:16] for name,dimension in stored):
            raise ValueError('Prepared signature differs from stored Chroma collection; old vectors preserved. Verify tokenizer compatibility before continuing.')
        atomic_json(ART/'units.json',units);atomic_json(ART/'chunks.json',chunks)
        stats={'status':'prepared','collection':'ipcc_'+signature[:16],'signature':signature,
            'pdf_sha256':manifest['source_sha256'],'embedding_model':'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
            'embedding_revision':'e8f8c211226b894fcb81acc59f3b34ba3efd5f42','dimensions':384,
            'physical_pages':len(pages),'text_pages':sum(bool(p['text'].strip()) for p in pages),
            'pages_with_units':len({u['page'] for u in units}),'unit_counts':dict(Counter(u['kind'] for u in units)),
            'chunk_count':len(chunks),
            **coverage_report(pages,units),
            'limitations':['Native labels/layout/tables are indexed; raster-only contents and colour-only/undigitized curve values are not automatically interpreted.',
                          'Auto table grids may contain merged headers; original PDF regions are authoritative.']}
        atomic_json(ART/'manifest.json',stats)
    result={'stage':'prepare','pages_processed_this_run':done,'prepared_pages':state['prepared_pages'],
            'total_pages':len(pages),'complete':state['next_page']>len(pages),
            'elapsed_seconds':round(time.monotonic()-start,2),'model_weights_loaded':False,
            'memory_mb':memory_mb()}
    atomic_json(ART/'last-job.json',result)
    return result


def embed(limit,max_seconds):
    from advanced.safety import atomic_json,guard,rest,memory_mb,claim_model,stop_requested
    began=time.monotonic();guard()
    manifest_path=ART/'manifest.json'
    if not manifest_path.exists():raise FileNotFoundError('Run bounded prepare stages until all pages are prepared first.')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    chunks=json.loads((ART/'chunks.json').read_text(encoding='utf-8'))
    import chromadb
    from chromadb.config import Settings
    client=chromadb.PersistentClient(path=str(ART/'chroma'),settings=Settings(anonymized_telemetry=False))
    collection=client.get_or_create_collection(manifest['collection'],embedding_function=None,
        configuration={'hnsw':{'space':'cosine','ef_search':50,'num_threads':1}})
    collection.modify(configuration={'hnsw':{'num_threads':1}})
    existing=set(collection.get(include=[])['ids'])
    expected={c['id'] for c in chunks}
    if not existing<=expected:raise ValueError('Stored chunks differ from prepared corpus; stop without overwriting.')
    missing=[c for c in chunks if c['id'] not in existing]
    if missing:
        claim_model('embedding')
        from local_embeddings import LocalEmbedder
        model=LocalEmbedder(batch_size=1,cpu_threads=1)
        guard()
    start=time.monotonic();done=0;peak=memory_mb()['rss'] or 0
    for c in missing[:limit]:
        if stop_requested() or time.monotonic()-start>=max_seconds:break
        measured=guard();peak=max(peak,measured['rss'] or 0)
        vector=model.embed_query(c['text'])
        measured=guard();peak=max(peak,measured['rss'] or 0)
        collection.upsert(ids=[c['id']],documents=[c['text']],embeddings=[vector],metadatas=[c['metadata']])
        done+=1
        atomic_json(ART/'embed-state.json',{'completed':len(existing)+done,'total':len(chunks),
                    'last_chunk':c['id'],'collection':collection.name,'batch_size':1,'cpu_threads':1})
        rest()
    count=collection.count()
    manifest.update(status='success' if count==len(chunks) else 'embedding_partial',
                    collection=collection.name,indexed_chunks=count)
    atomic_json(manifest_path,manifest)
    result={'stage':'embed','embedded_this_run':done,'indexed_chunks':count,'total_chunks':len(chunks),
            'complete':count==len(chunks),'batch_size':1,'cpu_threads':1,'peak_rss_mb':peak,
            'work_seconds':round(time.monotonic()-start,2),'total_seconds':round(time.monotonic()-began,2),
            'memory_mb':memory_mb()}
    atomic_json(ART/'last-job.json',result)
    return result


def status():
    import sqlite3
    from contextlib import closing
    result={'stage':'status','model_weights_loaded':False}
    for name in ('prepare-state.json','embed-state.json','manifest.json','last-job.json'):
        path=ART/name
        if path.exists():result[name]=json.loads(path.read_text(encoding='utf-8'))
    db=ART/'chroma/chroma.sqlite3'
    if db.exists():
        with closing(sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
            result['stored_collections']=conn.execute('SELECT name,dimension FROM collections').fetchall()
            result['stored_embeddings']=conn.execute('SELECT COUNT(*) FROM embeddings').fetchone()[0]
    return result


def main():
    from advanced.safety import apply_limits,profile,single_worker,guard,stop_requested,atomic_json
    cfg=profile();limits=apply_limits()
    parser=argparse.ArgumentParser(description='Bounded IPCC stages. Default status never loads a model.')
    parser.add_argument('--stage',choices=['status','prepare','embed'],default='status')
    parser.add_argument('--limit',type=int)
    parser.add_argument('--max-seconds',type=int,default=cfg['max_work_seconds'])
    args=parser.parse_args()
    limit=args.limit if args.limit is not None else (cfg['prepare_pages_per_run'] if args.stage=='prepare' else cfg['embedding_chunks_per_run'])
    if limit<1 or limit>64 or not 1<=args.max_seconds<=60:parser.error('limit must be 1..64; max-seconds must be 1..60')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['ANONYMIZED_TELEMETRY']='False'
    with single_worker():
        if args.stage!='status' and stop_requested():
            print('STOP file detected; no model loaded. Checkpoints retained.');return
        try:
            if args.stage!='status':guard()
            result=status() if args.stage=='status' else prepare(limit,args.max_seconds) if args.stage=='prepare' else embed(limit,args.max_seconds)
        except Exception as exc:
            if args.stage!='status':atomic_json(ART/'last-job.json',{'stage':args.stage,'status':'error',
                'error':{'type':type(exc).__name__,'message':str(exc)},'checkpoint_preserved':True})
            raise
    result['resource_limits']=limits
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
