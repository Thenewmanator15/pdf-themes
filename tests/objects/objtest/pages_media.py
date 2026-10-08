"""Page for multimedia and 3D: Screen, RichMedia, Movie, Sound, 3D and Projection
annotations, and the actions that drive them."""
import os

from PIL import Image
from pikepdf import Array, Dictionary, Name, String

from .core import Page, circle_path, n, poly_path, rect_path, round_rect_path
from .pages_annots import DATE, ap_form, markup
from .pages_interactive import label, link

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def asset(name):
    return open(os.path.join(ASSETS, name), "rb").read()


def poster(doc, w, h, caption):
    """A poster frame: the video still (stays) with a play badge and frame (swap)."""
    pal = doc.pal
    im = Image.open(os.path.join(ASSETS, "poster.png")).convert("RGB")
    img = doc.once("poster-img", lambda: doc.stream(im.tobytes(), Type=Name.XObject, Subtype=Name.Image,
                                                     Width=im.width, Height=im.height, ColorSpace=Name.DeviceRGB,
                                                     BitsPerComponent=8))
    bold = doc.fonts.get("SansBold")
    r = min(w, h) * 0.16
    body = ("q %s 0 0 %s 0 0 cm /Im Do Q %s %s f %s %s f %s 1.5 w %s S %s %s f BT /SansBold 7 Tf %s 4 4 Td %s Tj ET" % (
        n(w), n(h), pal.rg("accent"), circle_path(w / 2, h / 2, r), pal.rg("paper"),
        poly_path([(w / 2 - r * 0.35, h / 2 - r * 0.5), (w / 2 + r * 0.55, h / 2), (w / 2 - r * 0.35, h / 2 + r * 0.5)], close=True),
        pal.RG("rule"), rect_path(0.75, 0.75, w - 1.5, h - 1.5), pal.rg("ink"), rect_path(0, 0, bold.width(caption, 7) + 8, 14),
        pal.rg("paper"), bold.enc(caption)))
    return doc.form(body, [0, 0, w, h], Dictionary(XObject=Dictionary(Im=img), Font=Dictionary(SansBold=bold.obj)))


def page_media(doc, res):
    p = Page(doc, "Multimedia and 3D",
             "Video, sound and a 3D model. The media themselves stay as they are, but their posters and frames, "
             "the floating window's background (B), and the 3D view's background, render mode, cross-section "
             "and measurement colours all belong to the theme.")
    pal = p.pal
    t = p.grid(3, 4)
    clip = doc.embed_file("clip.mp4", asset("clip.mp4"), "video/mp4", "Test pattern video, 3 seconds")

    # 1 Screen annotation with a rendition
    x, y, w, h = p.tile(t[0], "Screen with a Rendition action", "T190, T218, T282, T293", "swaps",
                        note="MediaScreenParams B is the window background")
    r = [x + 4, y + 4, x + w - 4, y + 4 + (w - 8) * 9 / 16]
    rw, rh = r[2] - r[0], r[3] - r[1]
    clipdata = Dictionary(Type=Name.MediaClip, S=Name.MCD, N=String("Test pattern"), CT=String("video/mp4"), D=clip,
                          P=Dictionary(Type=Name.MediaPermissions, TF=String("TEMPACCESS")))
    rendition = doc.pdf.make_indirect(Dictionary(
        Type=Name.Rendition, S=Name.MR, N=String("Test pattern rendition"), C=clipdata,
        P=Dictionary(Type=Name.MediaPlayParams, BE=Dictionary(C=True, A=True, RC=1)),
        SP=Dictionary(Type=Name.MediaScreenParams,
                      BE=Dictionary(W=0, B=doc.rgb("paper"), O=1.0, M=0,
                                    F=Dictionary(Type=Name.FWParams, D=Array([384, 216]), P=4, RT=0, T=True,
                                                 UC=True, R=0, TT=Array([String(""), String("Test pattern")]))))))
    screen = markup(p, "Screen", r, "Video: test pattern", poster(doc, rw, rh, "Screen"), T=String("Test pattern video"),
                    MK=Dictionary(BG=doc.rgb("paper"), BC=doc.rgb("rule")))
    screen.A = Dictionary(S=Name.Rendition, R=rendition, AN=screen, OP=0)

    # 2 Rendition action from a link, and play controls
    x, y, w, h = p.tile(t[1], "Rendition actions: play, pause, stop", "T218", "viewer")
    for i, (txt, op) in enumerate([("Play the video", 0), ("Pause", 2), ("Resume", 3), ("Stop", 1)]):
        ly = y + h - 14 - i * 18
        tw = label(p, x + 6, ly, txt)
        act = Dictionary(S=Name.Rendition, AN=screen, OP=op)
        if op == 0:
            act.R = rendition
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], act, contents=txt)

    # 3 RichMedia
    x, y, w, h = p.tile(t[2], "RichMedia (video)", "T333, T334, T335, T338, T339, T340, T341, T342, T222", "swaps",
                        note="Opens in a floating window when activated")
    r = [x + 4, y + 4, x + w - 4, y + 4 + (w - 8) * 9 / 16]
    rw, rh = r[2] - r[0], r[3] - r[1]
    inst = doc.pdf.make_indirect(Dictionary(Type=Name.RichMediaInstance, Subtype=Name.Video, Asset=clip))
    cfg = doc.pdf.make_indirect(Dictionary(Type=Name.RichMediaConfiguration, Subtype=Name.Video, Name=String("Video"),
                                           Instances=Array([inst])))
    content = Dictionary(Type=Name.RichMediaContent, Assets=Dictionary(Names=Array([String("clip.mp4"), clip])),
                         Configurations=Array([cfg]))
    window = Dictionary(Type=Name.RichMediaWindow, Width=Dictionary(Default=384, Max=768, Min=192),
                        Height=Dictionary(Default=216, Max=432, Min=108),
                        Position=Dictionary(Type=Name.RichMediaPosition, HAlign=Name.Near, VAlign=Name.Near,
                                            HOffset=18, VOffset=18))
    presentation = Dictionary(Type=Name.RichMediaPresentation, Style=Name.Windowed, Window=window, Transparent=False,
                              NavigationPane=False, Toolbar=True, PassContextClick=False)
    settings = Dictionary(Type=Name.RichMediaSettings,
                          Activation=Dictionary(Type=Name.RichMediaActivation, Condition=Name.XA, Configuration=cfg,
                                                Presentation=presentation),
                          Deactivation=Dictionary(Type=Name.RichMediaDeactivation, Condition=Name.XD))
    rich = markup(p, "RichMedia", r, "RichMedia video", poster(doc, rw, rh, "RichMedia"),
                  RichMediaContent=content, RichMediaSettings=settings)
    ly = y + h - 14
    tw = label(p, x + 6, ly, "RichMediaExecute: play")
    link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9],
         Dictionary(S=Name.RichMediaExecute, TA=rich, TI=inst,
                    CMD=Dictionary(Type=Name.RichMediaCommand, C=String("play"))), contents="Play the RichMedia video")

    # 4 Movie (deprecated)
    x, y, w, h = p.tile(t[3], "Movie annotation (deprecated)", "T189, T306, T307, T213", "swaps",
                        note="Movie action plays it")
    r = [x + 4, y + 4, x + w - 4, y + 4 + (w - 8) * 9 / 16]
    rw, rh = r[2] - r[0], r[3] - r[1]
    movie = markup(p, "Movie", r, "Movie annotation", poster(doc, rw, rh, "Movie"), T=String("Test movie"),
                   Movie=Dictionary(F=clip, Aspect=Array([192, 108]), Poster=True),
                   A=Dictionary(ShowControls=True, Mode=Name.Once, Volume=0.5))
    ly = y + h - 14
    tw = label(p, x + 6, ly, "Movie action: play")
    link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.Movie, Annotation=movie, Operation=Name.Play),
         contents="Play the movie")

    # 5 Sound (deprecated)
    x, y, w, h = p.tile(t[4], "Sound annotation and action (deprecated)", "T188, T305, T212", "swaps",
                        note="A 440 Hz tone; the speaker icon swaps")
    snd = doc.once("sound", lambda: doc.stream(asset("tone.raw"), Type=Name.Sound, R=8000, C=1, B=8, E=Name.Raw))
    icon = ap_form(doc, 22, 22, "%s %s f %s 1.5 w 1 J 15 7 m 18 10 18 12 15 15 c S 17 4 m 22 9 22 13 17 18 c S" % (
        pal.rg("accent"), poly_path([(2, 8), (7, 8), (12, 3), (12, 19), (7, 14), (2, 14)], close=True), pal.RG("accent")))
    markup(p, "Sound", [x + 8, y + h / 2 - 11, x + 30, y + h / 2 + 11], "A 440 Hz tone", icon, Sound=snd,
           Name=Name.Speaker, C=doc.rgb("accent"))
    ly = y + h / 2 - 3
    tw = label(p, x + 40, ly, "Sound action: play")
    link(p, [x + 38, ly - 3, x + 42 + tw, ly + 9], Dictionary(S=Name.Sound, Sound=snd, Volume=1.0), contents="Play the tone")

    # 6-8 3D
    x, y, w, h = p.tile(t[5], "3D annotation (U3D)", "T309, T310, T311, T315, T317, T318, T320, T322, T323, T326-T331",
                        "swaps", note="3 views: BG, RM, LS, a section, a node, 5 measures")
    r = [x + 4, y + 4, x + w - 4, y + h - 2]
    rw, rh = r[2] - r[0], r[3] - r[1]

    def rgb4(role):
        return Array([Name.DeviceRGB] + [round(v, 4) for v in pal.rgb(role)])

    measure = doc.pdf.make_indirect(Dictionary(
        Type=Name("/3DMeasure"), Subtype=Name.LD3, TRL=String("Box length"), AP=Array([0, 0, 0]),
        A1=Array([-5, -20, 10]), N1=String("Box01"), A2=Array([-5, 20, 10]), N2=String("Box01"),
        TP=Array([0, 0, 14]), TY=Array([0, 1, 0]), TS=12, C=doc.rgb("orange"), V=40, U=String("mm"), P=1))
    comment = doc.pdf.make_indirect(Dictionary(Type=Name("/3DMeasure"), Subtype=Name("/3DC"), A1=Array([5, 20, 10]),
                                               N1=String("Box01"), TP=Array([12, 24, 12]), TB=Array([40, 14]), TS=10,
                                               C=doc.rgb("purple"), UT=String("Top corner")))
    m3 = lambda **kw: doc.pdf.make_indirect(Dictionary(Type=Name("/3DMeasure"), **kw))
    angle = m3(Subtype=Name.AD3, TRL=String("Corner angle"), AP=Array([0, 0, 0]), A1=Array([-5, -20, 0]), D1=Array([1, 0, 0]),
               A2=Array([-5, -20, 0]), D2=Array([0, 1, 0]), TP=Array([-2, -18, 0]), TX=Array([1, 0, 0]), TY=Array([0, 1, 0]),
               TS=10, C=doc.rgb("green"), V=90, P=0, DR=True)
    radius = m3(Subtype=Name.RD3, TRL=String("Radius"), AP=Array([0, 0, 0]), A1=Array([0, 0, 10]), A2=Array([5, 0, 10]),
                TP=Array([3, 2, 10]), TX=Array([1, 0, 0]), TY=Array([0, 1, 0]), TS=10, C=doc.rgb("blue"), V=5,
                U=String("mm"), P=1, R=True)
    perp = m3(Subtype=Name.PD3, TRL=String("Height"), AP=Array([0, 0, 0]), A1=Array([5, 20, 0]), A2=Array([5, 20, 10]),
              D1=Array([0, 0, 1]), TP=Array([7, 20, 5]), TY=Array([0, 0, 1]), TS=10, C=doc.rgb("pink"), V=10,
              U=String("mm"), P=1)
    lights = "Night" if pal.dark else "White"
    views = Array([
        Dictionary(Type=Name("/3DView"), XN=String("Default"), IN=String("Default view"), MS=Name.U3D,
                   U3DPath=String("DefaultView"), BG=Dictionary(Type=Name("/3DBG"), Subtype=Name.SC, CS=Name.DeviceRGB,
                                                                C=doc.rgb("paper")),
                   RM=Dictionary(Type=Name("/3DRenderMode"), Subtype=Name.Solid),
                   LS=Dictionary(Type=Name("/3DLightingScheme"), Subtype=Name("/" + lights)),
                   MA=Array([measure, comment, angle, radius, perp])),
        Dictionary(Type=Name("/3DView"), XN=String("Wireframe"), IN=String("Wireframe"), MS=Name.U3D,
                   U3DPath=String("DefaultView"), BG=Dictionary(Type=Name("/3DBG"), Subtype=Name.SC, C=doc.rgb("tile")),
                   RM=Dictionary(Type=Name("/3DRenderMode"), Subtype=Name.SolidWireframe, AC=rgb4("ink"), FC=Name.BG,
                                 O=0.6, CV=45),
                   LS=Dictionary(Type=Name("/3DLightingScheme"), Subtype=Name.CAD),
                   NA=Array([Dictionary(Type=Name("/3DNode"), N=String("Box01"), O=0.8, V=True,
                                        RM=Dictionary(Type=Name("/3DRenderMode"), Subtype=Name.ShadedIllustration,
                                                      AC=rgb4("accent"), FC=rgb4("tile")))])),
        Dictionary(Type=Name("/3DView"), XN=String("Section"), IN=String("Cross section"), MS=Name.U3D,
                   U3DPath=String("DefaultView"), BG=Dictionary(Type=Name("/3DBG"), Subtype=Name.SC, C=doc.rgb("paper")),
                   RM=Dictionary(Type=Name("/3DRenderMode"), Subtype=Name.Illustration, AC=rgb4("ink"), FC=rgb4("tile")),
                   LS=Dictionary(Type=Name("/3DLightingScheme"), Subtype=Name("/" + lights)),
                   SA=Array([Dictionary(Type=Name("/3DCrossSection"), C=Array([0, 0, 5]),
                                        O=Array([pikepdf_null(), 0, 0]), PO=0.5, PC=rgb4("accent"), IV=True,
                                        IC=rgb4("red"), ST=False, SC=False)])),
    ])
    views = Array([doc.pdf.make_indirect(v) for v in views])  # 3D views must be indirect (T311)
    stream3d = doc.stream(asset("simpleBox.u3d"), Type=Name("/3D"), Subtype=Name.U3D, VA=views, DV=0,
                          ColorSpace=res.icc("srgb"))
    bold = doc.fonts.get("SansBold")
    post = doc.form("%s %s f %s 1 w %s S %s %s f %s %s f %s %s f BT /SansBold 7 Tf %s 4 4 Td %s Tj ET" % (
        pal.rg("paper"), rect_path(0, 0, rw, rh), pal.RG("rule"), rect_path(0.5, 0.5, rw - 1, rh - 1),
        pal.rg("purple"), poly_path([(rw / 2 - 18, rh / 2 - 12), (rw / 2 + 6, rh / 2 - 22), (rw / 2 + 6, rh / 2 + 14), (rw / 2 - 18, rh / 2 + 24)], close=True),
        pal.rg("pink"), poly_path([(rw / 2 + 6, rh / 2 - 22), (rw / 2 + 20, rh / 2 - 14), (rw / 2 + 20, rh / 2 + 22), (rw / 2 + 6, rh / 2 + 14)], close=True),
        pal.rg("yellow"), poly_path([(rw / 2 - 18, rh / 2 + 24), (rw / 2 + 6, rh / 2 + 14), (rw / 2 + 20, rh / 2 + 22), (rw / 2 - 4, rh / 2 + 32)], close=True),
        pal.rg("ink"), bold.enc("3D model: click to activate")), [0, 0, rw, rh], Dictionary(Font=Dictionary(SansBold=bold.obj)))
    ann3d = markup(p, "3D", r, "3D model of a box", post, **{"3DD": stream3d, "3DV": 0,
                                                              "3DA": Dictionary(A=Name.PV, D=Name.PC, TB=True, NP=True,
                                                                                Style=Name.Embedded),
                                                              "3DI": True})

    note_icon = ap_form(doc, 18, 18, "%s %s f %s 1 w 4 11 m 14 11 l 4 7 m 11 7 l S" % (
        pal.rg("yellow"), round_rect_path(0, 0, 18, 18, 3), pal.RG("ink")))
    markup(p, "Text", [x + w - 26, y + h - 24, x + w - 8, y + h - 6], "A comment on the 3D model's default view",
           note_icon, C=doc.rgb("yellow"), Name=Name.Comment,
           ExData=Dictionary(Type=Name.ExData, Subtype=Name.Markup3D, **{"3DA": ann3d, "3DV": views[0]}))

    x, y, w, h = p.tile(t[6], "GoTo3DView actions, 3D markup", "T220, T173, T324", "viewer",
                        note="Switch views; the note at top right comments on view 1")
    for i, (txt, v) in enumerate([("Default view", 0), ("Wireframe view", 1), ("Cross-section view", 2)]):
        ly = y + h - 14 - i * 18
        tw = label(p, x + 6, ly, txt)
        link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.GoTo3DView, TA=ann3d, V=v), contents="Show the " + txt)

    x, y, w, h = p.tile(t[7], "Projection annotation (PDF 2.0)", "T172, T332, T327", "swaps",
                        note="Shows the 3D measurement on the page")
    r = [x + 6, y + h / 2 - 12, x + w - 6, y + h / 2 + 12]
    rw, rh = r[2] - r[0], r[3] - r[1]
    sans = doc.fonts.get("Sans")
    apb = "%s 1 w 4 6 m %s 6 l S %s %s %s BT /Sans 8 Tf %s %s 10 Td %s Tj ET" % (
        pal.RG("orange"), n(rw - 4), pal.rg("orange"),
        poly_path([(4, 6), (10, 9), (10, 3)], close=True) + " f",
        poly_path([(rw - 4, 6), (rw - 10, 9), (rw - 10, 3)], close=True) + " f", pal.rg("orange"),
        n(rw / 2 - sans.width("40 mm", 8) / 2), sans.enc("40 mm"))
    proj = markup(p, "Projection", r, "Projected measurement: 40 mm", ap_form(doc, rw, rh, apb, [sans]),
                  C=doc.rgb("orange"), ExData=Dictionary(Type=Name.ExData, Subtype=Name("/3DM"), M3DREF=measure))
    measure.S = proj

    # 9 Media on other platforms and rendition selectors
    x, y, w, h = p.tile(t[8], "Selector rendition with MH and BE", "T277, T278, T279, T283", "viewer",
                        note="Picks the first rendition the viewer can play")
    sel = doc.pdf.make_indirect(Dictionary(Type=Name.Rendition, S=Name.SR, N=String("Pick a format"),
                                           R=Array([rendition]),
                                           MH=Dictionary(C=Dictionary(Type=Name.MediaCriteria, A=True, D=Dictionary(V=8))),
                                           BE=Dictionary(C=Dictionary(Type=Name.MediaCriteria, O=True, S=False))))
    ly = y + h / 2
    tw = label(p, x + 6, ly, "Play through a selector")
    link(p, [x + 4, ly - 3, x + 8 + tw, ly + 9], Dictionary(S=Name.Rendition, R=sel, AN=screen, OP=4), contents="Play through a selector rendition")

    # 10 Floating window background
    x, y, w, h = p.tile(t[9], "Floating window colour", "T293, T294, T295", "swaps",
                        note="B is the background of the media window")
    p.figure("%s %s f %s 1 w %s S" % (pal.rg("paper"), round_rect_path(x + 10, y + 10, w - 20, h - 20, 6),
                                      pal.RG("rule"), round_rect_path(x + 10, y + 10, w - 20, h - 20, 6)),
             "A swatch of the media window background colour.")
    p.text(x + w / 2, y + h / 2 - 3, "B = paper colour", size=7, role="muted", tag="Caption", align="center")

    x, y, w, h = p.tile(t[10], "Embedded media files", "T43, T44, T45", "stays",
                        note="The MP4 and the tone are in the EmbeddedFiles tree")
    doc.embed_file("tone.wav", asset("tone.wav"), "audio/wav", "440 Hz tone")
    p.text(x + 6, y + h / 2 + 4, "clip.mp4, 12.8 kB", size=7.5, role="ink")
    p.text(x + 6, y + h / 2 - 10, "tone.wav, 4.8 kB", size=7.5, role="ink")

    x, y, w, h = p.tile(t[11], "What viewers show", "", "viewer")
    p.para(x + 2, y + h - 4, "Most viewers show only the posters here. Acrobat plays the video and the 3D model; "
           "pdf.js, Poppler, MuPDF and PDFium draw the posters and skip the media.", w - 4, size=6.5, role="muted")
    return p


def pikepdf_null():
    import pikepdf
    return pikepdf.Object.parse(b"null")
