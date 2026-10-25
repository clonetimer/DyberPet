#!/usr/bin/env python3
"""Visual audit snapshots from exactly pinned creator bytes, not generated art.

Emits two contact sheets as small base64 chunks in CI log for manual inspection.
No source assets are committed or repackaged into a release.
"""
import base64
import hashlib
import io
import math
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.install_artist_codex import SOURCES, ROOT as CODEX_ROOT, _download_pinned
from tools.install_creator_mascots import UPSTREAM, ROOT as MASCOT_ROOT, _download_pinned as mascot_fetch
from tools.install_artist_genshin import REPOSITORY, REVISION, SOURCE_IDENTITY, ROLES

def raw(url, limit=8_000_000):
    req = Request(url, headers={"User-Agent":"DyberPet-manual-image-inspection/1"})
    with urlopen(req, timeout=40) as response:
        result=response.read(limit+1)
    if len(result)>limit:
        raise ValueError("Source image exceeds limit: "+url)
    return result

def original_cell(data, index=0):
    with Image.open(io.BytesIO(data)) as sheet:
        sheet.load()
        if sheet.width!=1536 or sheet.height not in (1872,2288):
            raise ValueError("Unexpected original grid; refusing manual proxy")
        x=(index%8)*192
        y=(index//8)*208
        return sheet.convert("RGBA").crop((x,y,x+192,y+208))

def git_sha(rawdata):
    return hashlib.sha1(b"blob "+str(len(rawdata)).encode()+b"\0"+rawdata).hexdigest()

def native_frame(kind, name):
    anchor=next(path for path in SOURCE_IDENTITY[kind] if path.endswith(".png"))
    url=(f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/res/role/"
         +quote(name)+"/"+anchor)
    data=raw(url,limit=16_000_000)
    if git_sha(data)!=SOURCE_IDENTITY[kind][anchor]:
        raise ValueError("Native source frame mismatch "+kind)
    with Image.open(io.BytesIO(data)) as original:
        original.load()
        return original.convert("RGBA")

def base_pet(role, frame):
    with Image.open(ROOT/"res"/"role"/role/"action"/frame) as img:
        img.load()
        return img.convert("RGBA")

def contact_sheet(data, ncol, w=208,h=240):
    nrow=math.ceil(len(data)/ncol)
    out=Image.new("RGB",(w*ncol,h*nrow),(248,249,251))
    draw=ImageDraw.Draw(out)
    for index,(name,picture) in enumerate(data):
        x=(index%ncol)*w
        y=(index//ncol)*h
        draw.rectangle((x+2,y+2,x+w-3,y+h-3),outline=(200,207,219),width=1)
        draw.text((x+7,y+7),name,fill=(20,25,36))
        picture.thumbnail((w-28,h-55),Image.Resampling.LANCZOS)
        tile=Image.new("RGBA",(w-18,h-47),(255,255,255,255))
        tile.alpha_composite(picture,((tile.width-picture.width)//2,(tile.height-picture.height)//2))
        out.paste(tile.convert("RGB"),(x+9,y+28))
    return out

def announce(key,image):
    buf=io.BytesIO()
    image.save(buf,format="PNG",optimize=True)
    coded=base64.b64encode(buf.getvalue()).decode("ascii")
    print(f"VISUAL_AUDIT_IMAGE_START|{key}|{image.width}|{image.height}|{len(coded)}",flush=True)
    for i in range(0,len(coded),3500):
        print(f"VISUAL_AUDIT_CHUNK|{key}|{i//3500:04d}|{coded[i:i+3500]}",flush=True)
    print(f"VISUAL_AUDIT_IMAGE_END|{key}",flush=True)

def main():
    gs=[]
    for k,(id_,display,profile,manifest,atlas) in SOURCES.items():
        raw_atlas=_download_pinned(f"{CODEX_ROOT}/{id_}/spritesheet.webp",atlas)
        gs.append((k+" | "+id_,original_cell(raw_atlas)))
        print("SOURCE_CHECK_OK",k,id_,len(raw_atlas),flush=True)
    announce("CODEx12",contact_sheet(gs,3))

    others=[]
    for k,src in UPSTREAM.items():
        raw_atlas=mascot_fetch(f"{MASCOT_ROOT}/{src['id']}/spritesheet.webp",
                              src["atlas_sha256"],src["atlas_bytes"])
        others.append((k+" | "+src["id"],original_cell(raw_atlas)))
        print("SOURCE_CHECK_OK",k,src["id"],len(raw_atlas),flush=True)
    for k,(name,_profile,_label) in ROLES.items():
        others.append((k+" | original-native",native_frame(k,name)))
    others.append(("Kitty | bundled",base_pet("Kitty","stand_0.png")))
    others.append(("ChrisKitty | bundled",base_pet("ChrisKitty","stand_0.png")))
    announce("MASCOTS_NATIVE_BASE",contact_sheet(others,3))
    # Compare three entirely independent public Doro artists against the
    # quadrupedal Internet meme reference before selecting a default.
    doro_specs = (
        ("doro--godxxy1229",702066,"c8aeb0bfe877371f25d660b3d95a9e7e58191daf"),
        ("doro--lingxiaotian",2382142,"daaee2d9e75d16d94d71cd93a13d087cfbf49f2c"),
        ("doro--vaevie",2589654,"6b12f498f7db4e62e4f68a5b703a4af2ed9c56f9"),
    )
    options=[]
    for source_id,size,sha in doro_specs:
        payload=raw(f"{CODEX_ROOT}/{source_id}/spritesheet.webp")
        if len(payload)!=size or git_sha(payload)!=sha:
            raise ValueError("Doro alternate does not match pinned Git tree: "+source_id)
        for i,row in enumerate((0,1,2)):
            options.append((source_id+" / row "+str(row),original_cell(payload,8*row)))
        print("DORO_ALT_VERIFIED",source_id,size,flush=True)
    announce("DORO_ALTERNATIVES",contact_sheet(options,3))
    print("VISUAL_AUDIT_COMPLETE",len(gs)+len(others),flush=True)

if __name__=="__main__":
    main()
