"""Read palette data only. Never runs theme scripts or writes desktop configuration."""
import re
import tomllib
from pathlib import Path

PALETTE=Path.home()/'.local/state/omarchy/current/theme/colors.toml'
HEX=re.compile(r'#[0-9a-fA-F]{6}\Z')

def luminance(colour):
    rgb=[int(colour[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))

def contrast(a,b):
    x,y=sorted((luminance(a),luminance(b)))
    return (y+.05)/(x+.05)

def readable(candidate,backgrounds,ratio=4.5):
    if all(contrast(candidate,b)>=ratio for b in backgrounds):return candidate
    return max(('#000000','#ffffff'),key=lambda c:min(contrast(c,b) for b in backgrounds))

def palette(path=PALETTE):
    fallback=dict(background='#10131b',foreground='#edf0f8',accent='#c2b0ff')
    try:
        with open(path,'rb') as f: raw=f.read(65537)
        if len(raw)>65536:raise ValueError('Oversize palette')
        data=tomllib.loads(raw.decode())
        if not all(isinstance(data.get(k),str) and HEX.fullmatch(data[k]) for k in fallback):raise ValueError('Invalid palette')
        source='Omarchy palette'
    except (OSError,ValueError,UnicodeError):
        data=fallback;source='Fallback palette'
    bg=data['background'];fg=data['foreground'];accent=data['accent']
    # Use one surface luminance to guarantee contrast across cards and controls.
    return {'source':source,'mode':'light' if luminance(bg)>.179 else 'dark',
            'bg':bg,'panel':bg,'text':readable(fg,[bg]),'muted':readable(data.get('muted',fg) if HEX.fullmatch(str(data.get('muted',fg))) else fg,[bg]),
            'accent':readable(accent,[bg]),'line':readable(data.get('dark_foreground',fg) if HEX.fullmatch(str(data.get('dark_foreground',fg))) else fg,[bg],3)}

def css(path=PALETTE):
    p=palette(path); p['on-accent']=readable('#000000',[p['accent']])
    values=';'.join(f'--{k}:{p[k]}' for k in ('bg','panel','text','muted','accent','line','on-accent'))
    return ':root{color-scheme:'+p['mode']+';'+values+'}'
