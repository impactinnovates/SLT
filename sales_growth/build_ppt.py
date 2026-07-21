"""
sales_growth/build_ppt.py
Built-out consolidated deck: title, a 3-tier overview, one detail slide per
initiative (key decisions + 90-day actions + year-one milestones, tied to the
SLT tracker scope), and a closing / next-steps slide. Writes to Downloads.
Content comes from plan_data.PLAN so the deck, the Excel, and the List seed agree.
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from plan_data import PLAN

CORE  = RGBColor(0x00,0x67,0xB1); EXPAND=RGBColor(0xB8,0x79,0x1F); ENABLE=RGBColor(0x2E,0x7B,0x87)
INK   = RGBColor(0x1F,0x3A,0x4D); MUTE  = RGBColor(0x5A,0x6B,0x7A); FAINT=RGBColor(0x8595A3>>16 & 0xFF,0,0)
MUTE2 = RGBColor(0x6B,0x7B,0x8A); LIGHT=RGBColor(0xF1,0xF5,0xF9); WHITE=RGBColor(0xFF,0xFF,0xFF)
FONT  = "Segoe UI"
TIER_COLOR={"Core Play":CORE,"Expansion Bet":EXPAND,"Enabler":ENABLE}
TIER_LABEL={"Core Play":"TIER A  ·  CORE PLAY","Expansion Bet":"TIER B  ·  EXPANSION BET","Enabler":"TIER C  ·  ENABLER"}
SW, SH = Inches(13.333), Inches(7.5)


def _box(sl,l,t,w,h,fill=None,line=None):
    sh=sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,l,t,w,h)
    sh.shadow.inherit=False
    if fill is None: sh.fill.background()
    else: sh.fill.solid(); sh.fill.fore_color.rgb=fill
    if line is None: sh.line.fill.background()
    else: sh.line.color.rgb=line; sh.line.width=Pt(0.75)
    return sh


def _txt(sl,l,t,w,h,runs,size=12,bold=False,color=INK,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,
         font=FONT,space=4,line_spacing=1.0):
    tb=sl.shapes.add_textbox(l,t,w,h); tf=tb.text_frame; tf.word_wrap=True; tf.vertical_anchor=anchor
    if isinstance(runs,str): runs=[runs]
    for k,item in enumerate(runs):
        p=tf.paragraphs[0] if k==0 else tf.add_paragraph()
        p.alignment=align; p.space_after=Pt(space); p.space_before=Pt(0); p.line_spacing=line_spacing
        if isinstance(item,tuple): text,opts=item
        else: text,opts=item,{}
        r=p.add_run(); r.text=text
        r.font.size=Pt(opts.get("size",size)); r.font.bold=opts.get("bold",bold)
        r.font.name=opts.get("font",font); r.font.color.rgb=opts.get("color",color)
    return tb


def _footer(sl,page):
    _box(sl,0,SH-Inches(0.42),SW,Inches(0.42),fill=RGBColor(0xF7,0xF9,0xFB))
    _txt(sl,Inches(0.5),SH-Inches(0.40),Inches(10),Inches(0.3),
         "IEG Sales Growth  ·  Consolidated Plan  ·  feeds the SLT Strategic Initiatives tracker",
         size=8.5,color=MUTE2)
    _txt(sl,SW-Inches(1.2),SH-Inches(0.40),Inches(0.9),Inches(0.3),str(page),size=8.5,color=MUTE2,align=PP_ALIGN.RIGHT)


def _blank(prs):
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    _box(sl,0,0,SW,SH,fill=WHITE)
    return sl


def _fmt_money(v):
    if not v: return None
    return f"${v/1e6:.1f}M" if v<1e6*100 else f"${v/1e6:.0f}M"


# ---------------------------------------------------------------- title
def title_slide(prs):
    sl=_blank(prs)
    _box(sl,0,0,Inches(0.28),SH,fill=CORE)
    _txt(sl,Inches(0.9),Inches(1.6),Inches(11),Inches(0.5),
         "IEG SALES GROWTH STRATEGY WORKSHOP  ·  JULY 2026",size=13,bold=True,color=CORE)
    _txt(sl,Inches(0.85),Inches(2.15),Inches(11.6),Inches(1.6),
         [("The Consolidated Plan",{"size":46,"bold":True,"color":INK})])
    _txt(sl,Inches(0.9),Inches(3.5),Inches(11),Inches(1.0),
         "Every idea from the six SLT decks, consolidated into 12 initiatives across three tiers, "
         "with the key decisions and the 90-day and year-one actions to move each one.",
         size=16,color=MUTE)
    for k,(lab,col) in enumerate([("3 Core Plays",CORE),("6 Expansion Bets",EXPAND),("3 Enablers",ENABLE)]):
        x=Inches(0.9+k*3.9)
        _box(sl,x,Inches(4.9),Inches(3.5),Inches(0.9),fill=col)
        _txt(sl,x,Inches(5.02),Inches(3.5),Inches(0.7),lab,size=18,bold=True,color=WHITE,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
    _txt(sl,Inches(0.9),Inches(6.15),Inches(11.5),Inches(0.5),
         "Now an actionable plan that populates the SLT Strategic Initiatives tracker (Sponsor / Owner / Task).",
         size=12,color=MUTE2)
    return sl


# ---------------------------------------------------------------- overview
def overview_slide(prs):
    sl=_blank(prs)
    _txt(sl,Inches(0.5),Inches(0.35),Inches(12),Inches(0.6),
         [("The plan at a glance",{"size":30,"bold":True,"color":INK})])
    _txt(sl,Inches(0.5),Inches(1.02),Inches(12.3),Inches(0.5),
         "All six leaders independently prioritized selling deeper into existing customers and growing recurring service. "
         "The three tiers put that consensus first, the bigger bets second, and the enablers underneath.",size=12,color=MUTE)
    tiers=[("Core Play",CORE),("Expansion Bet",EXPAND),("Enabler",ENABLE)]
    x0=Inches(0.5); colw=Inches(4.05); gap=Inches(0.18); top=Inches(1.75)
    for c,(tier,col) in enumerate(tiers):
        x=Emu(int(x0)+c*(int(colw)+int(gap)))
        _box(sl,x,top,colw,Inches(0.5),fill=col)
        _txt(sl,x,top+Inches(0.04),colw,Inches(0.42),TIER_LABEL[tier],size=11.5,bold=True,color=WHITE,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
        y=int(top)+int(Inches(0.62))
        for i in [z for z in PLAN if z["tier"]==tier]:
            ch=Inches(1.02)
            _box(sl,x,Emu(y),colw,ch,fill=LIGHT); _box(sl,x,Emu(y),Inches(0.08),ch,fill=col)
            money=_fmt_money(i["rev"]) or "sized in diligence"
            _txt(sl,x+Inches(0.2),Emu(y)+Inches(0.06),colw-Inches(0.3),Inches(0.4),
                 [(f"{i['code']}  {i['name']}",{"size":11.5,"bold":True,"color":INK})],line_spacing=0.95)
            _txt(sl,x+Inches(0.2),Emu(y)+Inches(0.60),colw-Inches(0.3),Inches(0.4),
                 [(f"Sponsor {i['sponsor'].split()[0]} · Owner {i['owner'].split()[0]}   ",{"size":9.5,"color":MUTE2}),
                  (money+" target",{"size":9.5,"bold":True,"color":col})])
            y+=int(ch)+int(Inches(0.1))
    _footer(sl,2)
    return sl


# ---------------------------------------------------------------- detail
def detail_slide(prs,i,page):
    sl=_blank(prs); col=TIER_COLOR[i["tier"]]
    _box(sl,0,0,SW,Inches(1.35),fill=col)
    _txt(sl,Inches(0.5),Inches(0.18),Inches(11),Inches(0.3),TIER_LABEL[i["tier"]],size=11,bold=True,color=WHITE)
    _txt(sl,Inches(0.5),Inches(0.46),Inches(11.4),Inches(0.8),
         [(f"{i['code']}   {i['name']}",{"size":24,"bold":True,"color":WHITE})],line_spacing=0.95)
    money=_fmt_money(i["rev"])
    chip = (money+" revenue target") if money else "Target sized in diligence"
    if i["ebitda"]: chip += f"  ·  {_fmt_money(i['ebitda'])} EBITDA"
    _txt(sl,SW-Inches(4.3),Inches(0.2),Inches(3.9),Inches(0.35),chip,size=12,bold=True,color=WHITE,align=PP_ALIGN.RIGHT)

    # meta line
    _txt(sl,Inches(0.5),Inches(1.5),Inches(12.3),Inches(0.35),
         [(f"Sponsor: ",{"size":11,"color":MUTE2}),(i["sponsor"],{"size":11,"bold":True,"color":INK}),
          ("     Owner: ",{"size":11,"color":MUTE2}),(i["owner"],{"size":11,"bold":True,"color":INK}),
          ("     Priority: ",{"size":11,"color":MUTE2}),(i["priority"],{"size":11,"bold":True,"color":INK}),
          ("     Region: ",{"size":11,"color":MUTE2}),(i["region"],{"size":11,"bold":True,"color":INK}),
          ("     Contributors: ",{"size":11,"color":MUTE2}),(", ".join(n.split()[0] for n in i["contributors"]),{"size":11,"color":INK})])
    _txt(sl,Inches(0.5),Inches(1.9),Inches(12.3),Inches(0.6),i["desc"],size=12,color=MUTE,line_spacing=1.05)

    # left: key decisions
    ly=Inches(2.75)
    _box(sl,Inches(0.5),ly,Inches(4.5),Inches(0.34),fill=col)
    _txt(sl,Inches(0.5),ly+Inches(0.02),Inches(4.5),Inches(0.32),"KEY DECISIONS",size=12,bold=True,color=WHITE,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
    _txt(sl,Inches(0.55),ly+Inches(0.5),Inches(4.45),Inches(3.4),
         [(f"•  {d}",{"size":12.5,"color":INK}) for d in i["decisions"]],space=10,line_spacing=1.02)

    # right: 90-day + year
    rx=Inches(5.35)
    _box(sl,rx,ly,Inches(7.45),Inches(0.34),fill=INK)
    _txt(sl,rx,ly+Inches(0.02),Inches(7.45),Inches(0.32),"FIRST 90 DAYS",size=12,bold=True,color=WHITE,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
    d90=[(n,due) for n,p,due in i["tasks"] if p=="90d"]
    dyr=[(n,due) for n,p,due in i["tasks"] if p=="year"]
    _txt(sl,rx+Inches(0.05),ly+Inches(0.5),Inches(7.4),Inches(2.0),
         [(f"•  {n}   ({due[5:]})" if False else f"•  {n}",{"size":11.5,"color":INK}) for n,due in d90],space=7,line_spacing=1.02)
    yy=ly+Inches(0.5)+Emu(int(Inches(0.50))*len(d90))+Inches(0.30)
    _box(sl,rx,yy,Inches(7.45),Inches(0.34),fill=MUTE2)
    _txt(sl,rx,yy+Inches(0.02),Inches(7.45),Inches(0.32),"YEAR ONE",size=12,bold=True,color=WHITE,align=PP_ALIGN.CENTER,anchor=MSO_ANCHOR.MIDDLE)
    _txt(sl,rx+Inches(0.05),yy+Inches(0.5),Inches(7.4),Inches(1.4),
         [(f"•  {n}",{"size":11.5,"color":INK}) for n,due in dyr],space=7,line_spacing=1.02)

    # KPI strip
    _box(sl,Inches(0.5),Inches(6.55),Inches(12.33),Inches(0.5),fill=LIGHT)
    _txt(sl,Inches(0.65),Inches(6.62),Inches(12.1),Inches(0.4),
         [("KPI  ",{"size":11,"bold":True,"color":col}),(i["kpi"],{"size":11,"color":INK})],anchor=MSO_ANCHOR.MIDDLE)
    _footer(sl,page)
    return sl


# ---------------------------------------------------------------- closing
def closing_slide(prs,page):
    sl=_blank(prs)
    _box(sl,0,0,Inches(0.28),SH,fill=CORE)
    _txt(sl,Inches(0.85),Inches(0.6),Inches(11),Inches(0.7),
         [("From plan to tracker",{"size":30,"bold":True,"color":INK})])
    steps=[
      ("1.  Load the tracker","The 12 initiatives and their 58 tasks populate the SLT Strategic Initiatives List (Category BOD, Sponsor / Owner / Task), so progress rolls up on the live dashboard."),
      ("2.  Confirm owners + targets","Sponsors and Owners are set; the expansion-bet dollar targets are first-pass and get sized in the 90-day work. M&A stays unsized until diligence."),
      ("3.  Work the 90-day list","Each initiative's first-90-day actions are the near-term tasks. The three enablers (comp, pricing, demand engine) unblock the rest and start now."),
      ("4.  Resolve the four tensions","Pricing enforcement vs rebates; online containers vs the OEM channel; the core-parts aperture; discipline vs the bigger platform bets. Decide these to make the plan one voice."),
      ("5.  Report up","The dashboard's board view rolls the initiatives to the BOD; the tracker keeps Sponsor / Owner accountable between meetings."),
    ]
    y=Inches(1.7)
    for head,body in steps:
        _txt(sl,Inches(0.9),y,Inches(3.3),Inches(0.8),[(head,{"size":15,"bold":True,"color":CORE})])
        _txt(sl,Inches(4.3),y,Inches(8.4),Inches(0.9),body,size=12.5,color=INK,line_spacing=1.05)
        y+=Inches(1.02)
    _footer(sl,page)
    return sl


def build(path):
    prs=Presentation(); prs.slide_width=SW; prs.slide_height=SH
    title_slide(prs)
    overview_slide(prs)
    page=3
    for i in PLAN:
        detail_slide(prs,i,page); page+=1
    closing_slide(prs,page)
    try: prs.save(path)
    except PermissionError:
        path=path.replace(".pptx","_v2.pptx"); prs.save(path)
    return path,len(prs.slides._sldIdLst)


if __name__ == "__main__":
    out=os.path.join(os.path.expanduser("~"),"Downloads","IEG Sales Growth - Consolidated Plan.pptx")
    p,n=build(out)
    print(f"saved {p}  ({n} slides)")
