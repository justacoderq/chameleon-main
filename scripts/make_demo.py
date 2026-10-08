"""Create a short, silent MJPEG AVI walkthrough from actual evaluation PNGs.

This is an engine preview, not a recording of a working Express session.
Uses Pillow and the AVI container format; no external encoder is needed.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import struct
from PIL import Image, ImageDraw, ImageFont, ImageOps


def chunk(tag, data):
    return tag + struct.pack("<I",len(data)) + data + (b"\0" if len(data)%2 else b"")


def write_avi(path, frames, width=1280, height=720, fps=2):
    avih = struct.pack("<14I",1_000_000//fps,max(map(len,frames))*fps,0,16,len(frames),0,1,max(map(len,frames)),width,height,0,0,0,0)
    strh = struct.pack("<4s4sIHH8I4h",b"vids",b"MJPG",0,0,0,0,1,fps,0,len(frames),max(map(len,frames)),0xffffffff,0,0,0,width,height)
    strf = struct.pack("<IiiHH4sIiiII",40,width,height,1,24,b"MJPG",width*height*3,0,0,0,0)
    headers = chunk(b"LIST",b"hdrl"+chunk(b"avih",avih)+chunk(b"LIST",b"strl"+chunk(b"strh",strh)+chunk(b"strf",strf)))
    movie, index, offset = [],[],4
    for frame in frames:
        part = chunk(b"00dc",frame)
        movie.append(part)
        index.append(struct.pack("<4sIII",b"00dc",16,offset,len(frame)))
        offset += len(part)
    data = b"AVI "+headers+chunk(b"LIST",b"movi"+b"".join(movie))+chunk(b"idx1",b"".join(index))
    path.write_bytes(b"RIFF"+struct.pack("<I",len(data))+data)
    # Verify the actual JPEG frames and the file's container length.
    for frame in frames:
        with Image.open(BytesIO(frame)) as image:
            assert image.size == (width,height)
            image.verify()
    assert path.stat().st_size == len(data)+8


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,default=Path("output/model-samples"))
    p.add_argument("--output",type=Path,default=Path("output/demo/chameleon-engine-demo.avi"))
    args = p.parse_args()
    report = json.loads((args.input/"report.json").read_text())
    frames = []
    def canvas(title,subtitle):
        image = Image.new("RGB",(1280,720),"#f6f5ef")
        draw = ImageDraw.Draw(image)
        draw.text((48,28),"CHAMELEON / BASELINE",font=ImageFont.load_default(size=20),fill="#386044")
        draw.text((48,70),title,font=ImageFont.load_default(size=40),fill="#202b25")
        draw.text((48,128),subtitle,font=ImageFont.load_default(size=19),fill="#546158")
        draw.text((48,680),"Development rendering | Original assets | Local CPU model | Not a live Express recording",font=ImageFont.load_default(size=15),fill="#546158")
        return image,draw
    for case in report["cases"]:
        name = case["name"]
        image,draw = canvas(name.replace("chameleon_sample_","").replace("_"," "),"Original design on the left. Automatically adapted design on the right.")
        for suffix,rect in [("source",(48,190,440,450)),("result",(540,190,692,390))]:
            with Image.open(args.input/f"{name}-{suffix}.png") as src:
                thumb = ImageOps.contain(src,rect[2:])
                image.paste(thumb,(rect[0]+(rect[2]-thumb.width)//2,rect[1]+(rect[3]-thumb.height)//2))
        small = case["audit"].get("small_texts",0)
        note = f"Elements retained. Text below 10px: {small}." + (" Extreme banners remain a readability limitation." if small else " No measured overflow.")
        draw.text((540,610),note[:90],font=ImageFont.load_default(size=16),fill="#202b25")
        stream = BytesIO();image.save(stream,format="JPEG",quality=90)
        frames.extend([stream.getvalue()]*12)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    write_avi(args.output,frames)
    print(f"Created {args.output}: {len(frames)/2:.0f}s, {len(frames)} verified JPEG frames. Playback still needs a video player.")


if __name__ == "__main__":
    main()
