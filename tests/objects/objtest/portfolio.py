"""A PDF portfolio (portable collection) in light and dark: the Collection's colour
dictionary, schema, folders, sort and split, plus a cover page in theme colours."""
import io

import pikepdf
from pikepdf import Array, Dictionary, Name, String

from .core import Doc, Page, MARGIN, H, W, rect_path, round_rect_path
from .images import photo
from .palette import build_palettes


def tiny_doc(pal, title, role):
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(300, 200))
    r, g, b = pal.rgb("paper")
    a, b2, c = pal.rgb(role)
    page.obj.Contents = pdf.make_stream(("%.3f %.3f %.3f rg 0 0 300 200 re f %.3f %.3f %.3f rg 30 30 240 140 re f"
                                         % (r, g, b, a, b2, c)).encode())
    pdf.docinfo.Title = title
    buf = io.BytesIO()
    pdf.save(buf, deterministic_id=True)
    return buf.getvalue()


def build_portfolio(pal):
    doc = Doc(pal)
    p = Page(doc, "PDF portfolio", "This file is a portable collection. Viewers that support portfolios show the "
             "attachments in their own layout, using the colours in the Collection's Colors dictionary; this cover "
             "page is what other viewers show.")
    y = H - 130
    for role, label in [("paper", "Background"), ("tile", "CardBackground"), ("rule", "CardBorder"),
                        ("ink", "PrimaryText"), ("muted", "SecondaryText")]:
        p.artifact("%s %s f %s 0.6 w %s S" % (pal.rg(role), round_rect_path(MARGIN, y - 4, 40, 16, 3), pal.RG("rule"),
                                              round_rect_path(MARGIN, y - 4, 40, 16, 3)))
        p.text(MARGIN + 50, y + 1, label, size=9)
        y -= 24
    doc.cover("Collection colours", "T153, T157", 1, "swaps")
    doc.cover("Collection schema, sort and folders", "T154, T155, T156, T159", 1, "viewer")
    pdf = doc.finish()

    def attach(name, data, mime, desc, fields):
        ef = pdf.make_stream(data)
        ef.Type = Name.EmbeddedFile
        ef.Subtype = Name("/" + mime.replace("/", "#2F"))
        ef.Params = Dictionary(Size=len(data), ModDate=String("D:20261003120000Z"))
        fs = pdf.make_indirect(Dictionary(Type=Name.Filespec, F=String(name), UF=String(name), Desc=String(desc),
                                          EF=Dictionary(F=ef, UF=ef), CI=Dictionary(Type=Name.CollectionItem, **fields)))
        return fs

    im = photo(120, 80)
    png = io.BytesIO()
    im.save(png, "PNG")
    # Attachments are separate files a theme can't reach, so they're the same in both builds.
    light, dark = build_palettes()
    files = [
        attach("light-sample.pdf", tiny_doc(light, "Sample one", "accent"), "application/pdf", "A one-page PDF",
               dict(Kind=String("PDF"), Order=1)),
        attach("dark-sample.pdf", tiny_doc(dark, "Sample two", "green"), "application/pdf", "Another one-page PDF",
               dict(Kind=String("PDF"), Order=2)),
        attach("landscape.png", png.getvalue(), "image/png", "A photo", dict(Kind=String("Image"), Order=3)),
        attach("palette.csv", ("role,light,dark\n" + "\n".join("%s,%s,%s" % (r, light.hexstr(r), dark.hexstr(r))
                                                               for r in ("paper", "ink", "accent"))).encode(),
               "text/csv", "The palette", dict(Kind=String("Data"), Order=4)),
    ]
    # Files in a folder are keyed "<ID>name" in the EmbeddedFiles tree (ISO 32000-2, 12.3.5).
    keyed = [("<1>" + str(fs.F) if str(fs.F).endswith("-sample.pdf") else str(fs.F), fs) for fs in files]
    names = Array()
    for key, fs in sorted(keyed, key=lambda kv: kv[0]):
        names.append(String(key))
        names.append(fs)
    pdf.Root.Names = pdf.Root.get("/Names", Dictionary())
    pdf.Root.Names.EmbeddedFiles = Dictionary(Names=names)

    root_folder = pdf.make_indirect(Dictionary(Type=Name.Folder, ID=0, Name=String("Portfolio")))
    sub = pdf.make_indirect(Dictionary(Type=Name.Folder, ID=1, Name=String("Samples"), Parent=root_folder))
    root_folder.Child = sub
    pdf.Root.Collection = Dictionary(
        Type=Name.Collection,
        Schema=Dictionary(Type=Name.CollectionSchema,
                          FileName=Dictionary(Type=Name.CollectionField, Subtype=Name.F, N=String("Name"), O=0),
                          Desc=Dictionary(Type=Name.CollectionField, Subtype=Name.Desc, N=String("Description"), O=1),
                          Kind=Dictionary(Type=Name.CollectionField, Subtype=Name.S, N=String("Kind"), O=2),
                          Order=Dictionary(Type=Name.CollectionField, Subtype=Name.N, N=String("Order"), O=3, V=False),
                          Size=Dictionary(Type=Name.CollectionField, Subtype=Name.Size, N=String("Size"), O=4)),
        D=String("<1>light-sample.pdf"), View=Name.D,
        Sort=Dictionary(Type=Name.CollectionSort, S=Name.Order, A=True),
        Colors=Dictionary(Type=Name.CollectionColors, Background=doc.rgb("paper"), CardBackground=doc.rgb("tile"),
                          CardBorder=doc.rgb("rule"), PrimaryText=doc.rgb("ink"), SecondaryText=doc.rgb("muted")),
        Folders=root_folder,
        Split=Dictionary(Type=Name.CollectionSplit, Direction=Name.H, Position=30))
    pdf.Root.PageMode = Name.UseAttachments
    return pdf
