"""Render visual pages and their neighbours, plus contact sheets for source QA."""
import json
from pathlib import Path

from advanced.inspect_pdf import PDF,OUT,dump


def main():
    import pymupdf
    from PIL import Image,ImageDraw
    pages=json.loads((OUT/'pages.json').read_text(encoding='utf-8'))
    selected=set()
    for p in pages:
        if p['captions']:
            selected.update(range(max(1,p['page']-1),min(len(pages),p['page']+1)+1))
        if p['drawing_count']>40 or p['image_count']>1:
            selected.add(p['page'])
    doc=pymupdf.open(PDF)
    for number in sorted(selected):
        path=OUT/'pages'/f'page-{number:03}.png'
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():doc[number-1].get_pixmap(dpi=110,alpha=False).save(path)
    numbers=sorted(selected)
    for i in range(0,len(numbers),12):
        sheet=Image.new('RGB',(1200,2320),'#dddddd')
        draw=ImageDraw.Draw(sheet)
        for j,number in enumerate(numbers[i:i+12]):
            with Image.open(OUT/'pages'/f'page-{number:03}.png') as original:
                thumb=original.copy();thumb.thumbnail((390,540))
                x=(j%3)*400;y=(j//3)*580
                draw.text((x+10,y+5),f'PDF physical page {number}',fill='black')
                sheet.paste(thumb,(x+(400-thumb.width)//2,y+25))
        sheet.save(OUT/f'contact-{i//12+1:02}.png')
    dump(OUT/'render_review.json',{'rendered_pages':numbers,'contact_sheets':(len(numbers)+11)//12})
    print('Rendered',len(numbers),'pages; contact sheets',(len(numbers)+11)//12)


if __name__=='__main__':main()
