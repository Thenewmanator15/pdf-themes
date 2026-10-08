"""The document and page builders shared by every page of the test.

A `Doc` holds one build (light or dark). Pages draw through `Page` helpers so
that every label is tagged, every tile looks the same, and the two builds
write the same operators in the same order with only the colours changed.
"""
import math
from collections import defaultdict

import pikepdf
from pikepdf import Array, Dictionary, Name, String

from .fonts import FontSet
from .palette import fmt

W, H = 595, 842
MARGIN = 36


def n(v):
    """Number for a content stream."""
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def rect_path(x, y, w, h):
    return "%s %s %s %s re" % (n(x), n(y), n(w), n(h))


def round_rect_path(x, y, w, h, r):
    k = 0.5523 * r
    return " ".join([
        "%s %s m" % (n(x + r), n(y)),
        "%s %s l" % (n(x + w - r), n(y)),
        "%s %s %s %s %s %s c" % (n(x + w - r + k), n(y), n(x + w), n(y + r - k), n(x + w), n(y + r)),
        "%s %s l" % (n(x + w), n(y + h - r)),
        "%s %s %s %s %s %s c" % (n(x + w), n(y + h - r + k), n(x + w - r + k), n(y + h), n(x + w - r), n(y + h)),
        "%s %s l" % (n(x + r), n(y + h)),
        "%s %s %s %s %s %s c" % (n(x + r - k), n(y + h), n(x), n(y + h - r + k), n(x), n(y + h - r)),
        "%s %s l" % (n(x), n(y + r)),
        "%s %s %s %s %s %s c" % (n(x), n(y + r - k), n(x + r - k), n(y), n(x + r), n(y)),
        "h"])


def circle_path(cx, cy, r):
    k = 0.5523 * r
    return " ".join([
        "%s %s m" % (n(cx + r), n(cy)),
        "%s %s %s %s %s %s c" % (n(cx + r), n(cy + k), n(cx + k), n(cy + r), n(cx), n(cy + r)),
        "%s %s %s %s %s %s c" % (n(cx - k), n(cy + r), n(cx - r), n(cy + k), n(cx - r), n(cy)),
        "%s %s %s %s %s %s c" % (n(cx - r), n(cy - k), n(cx - k), n(cy - r), n(cx), n(cy - r)),
        "%s %s %s %s %s %s c" % (n(cx + k), n(cy - r), n(cx + r), n(cy - k), n(cx + r), n(cy)),
        "h"])


def star_path(cx, cy, r_out, r_in, points=5, rot=90):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / points)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return poly_path(pts, close=True)


def poly_path(pts, close=False):
    out = ["%s %s m" % (n(pts[0][0]), n(pts[0][1]))]
    out += ["%s %s l" % (n(x), n(y)) for x, y in pts[1:]]
    if close:
        out.append("h")
    return " ".join(out)


class StructElem:
    def __init__(self, tag, page=None, mcid=None, alt=None, attrs=None, cls=None, title=None, actual=None, lang=None,
                 ns=None, expansion=None, sid=None):
        self.tag, self.page, self.mcid = tag, page, mcid
        self.alt, self.attrs, self.cls, self.title, self.actual, self.lang = alt, attrs, cls, title, actual, lang
        self.ns, self.expansion, self.sid = ns, expansion, sid
        self.children = []
        self.objr = None   # annotation object for OBJR
        self.obj = None


class Page:
    def __init__(self, doc, title, intro, *, label_style=None, mediabox=None, **opts):
        self.doc, self.pal, self.pdf = doc, doc.pal, doc.pdf
        self.number = len(doc.pages) + 1
        self.title, self.intro = title, intro
        self.page = self.pdf.add_blank_page(page_size=(W, H))
        self.obj = self.page.obj
        self.mediabox = mediabox or (0, 0, W, H)
        self.obj.MediaBox = Array(list(self.mediabox))
        self.ops = []
        self.res = defaultdict(dict)
        self.annots = []
        self.opts = opts
        self.footer_scale = 1.0 if self.mediabox[2] - self.mediabox[0] >= W else 0.5
        self.sect = StructElem("Sect", title=title or "Page %d" % self.number)
        doc.struct_root.children.append(self.sect)
        self.mcid_elems = []
        self.stack = [self.sect]
        doc.pages.append(self)
        self.paper()
        if title:
            self.header()

    # -- resources ---------------------------------------------------------------
    def font(self, key):
        f = self.doc.fonts.get(key)
        self.res["Font"][f.key] = f.obj
        return f

    def std(self, base):
        f = self.doc.fonts.standard(base)
        self.res["Font"][f.key] = f.obj
        return f

    def std_bare(self, base):
        f = self.doc.fonts.standard(base, bare=True)
        self.res["Font"][f.key] = f.obj
        return f

    def add_font(self, f):
        self.res["Font"][f.key] = f.obj
        return f

    def use(self, category, name, obj):
        self.res[category][name] = obj
        return "/" + name

    # -- content -----------------------------------------------------------------
    def put(self, *ops):
        self.ops.extend(ops)

    def fill(self, role):
        return self.pal.rg(role)

    def stroke(self, role):
        return self.pal.RG(role)

    def begin(self, tag, **kw):
        el = StructElem(tag, **kw)
        self.stack[-1].children.append(el)
        self.stack.append(el)
        return el

    def end(self):
        return self.stack.pop()

    def tagged(self, tag, body, alt=None, attrs=None, cls=None, actual=None, lang=None, extra="", **kw):
        mcid = len(self.mcid_elems)
        el = StructElem(tag, page=self, mcid=mcid, alt=alt, attrs=attrs, cls=cls, actual=actual, lang=lang, **kw)
        self.stack[-1].children.append(el)
        self.mcid_elems.append(el)
        props = "<</MCID %d%s>>" % (mcid, extra)
        self.put("/%s %s BDC" % (tag, props), "q", body, "Q", "EMC")
        return el

    def artifact(self, body, kind=None):
        if kind:
            self.put("/Artifact <</Type /%s>> BDC" % kind, "q", body, "Q", "EMC")
        else:
            self.put("/Artifact BMC", "q", body, "Q", "EMC")

    def text_op(self, x, y, s, size, f, role):
        return "BT /%s %s Tf %s %s %s Td %s Tj ET" % (f.key, n(size), self.fill(role), n(x), n(y), f.enc(s))

    def text(self, x, y, s, size=7.5, font="Sans", role="ink", tag="P", align="left", artifact=False):
        f = self.font(font)
        w = f.width(s, size)
        if align == "center":
            x -= w / 2
        elif align == "right":
            x -= w
        body = self.text_op(x, y, s, size, f, role)
        if artifact:
            self.artifact(body)
        elif tag:
            self.tagged(tag, body)
        else:
            self.put(body)
        return w

    def wrap(self, s, width, size, font="Sans"):
        f = self.doc.fonts.get(font)
        lines, cur = [], ""
        for word in s.split():
            trial = (cur + " " + word).strip()
            if f.width(trial, size) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def para(self, x, y, s, width, size=7.5, font="Sans", role="ink", leading=None, tag="P"):
        leading = leading or size * 1.3
        f = self.font(font)
        lines = self.wrap(s, width, size, font)
        body = ["BT /%s %s Tf %s TL %s %s %s Td" % (f.key, n(size), n(leading), self.fill(role), n(x), n(y))]
        for i, line in enumerate(lines):
            body.append(("%s Tj" if i == 0 else "T* %s Tj") % f.enc(line))
        body.append("ET")
        if tag:
            self.tagged(tag, "\n".join(body))
        else:
            self.put("\n".join(body))
        return y - leading * len(lines)

    # -- page furniture ----------------------------------------------------------
    def paper(self):
        x0, y0, x1, y1 = self.mediabox
        self.artifact("%s %s f" % (self.fill("paper"), rect_path(x0, y0, x1 - x0, y1 - y0)), "Background")

    def header(self):
        self.text(MARGIN, H - 52, "%d  %s" % (self.number, self.title), size=16, font="SansBold", tag="H1")
        if self.intro:
            self.para(MARGIN, H - 68, self.intro, W - 2 * MARGIN, size=8, role="muted")

    def footer(self):
        f = self.font("Sans")
        x0, x1 = max(0, self.mediabox[0]) + MARGIN * self.footer_scale, min(W, self.mediabox[2]) - MARGIN * self.footer_scale
        size = 6.5 * self.footer_scale
        body = "%s %s" % (self.text_op(x0, 22 * self.footer_scale, "PDF objects test for colour themes", size, f, "muted"),
                          self.text_op(x1 - f.width("page %d" % self.number, size), 22 * self.footer_scale,
                                       "page %d" % self.number, size, f, "muted"))
        self.put("/Artifact <</Type /Pagination /Subtype /Footer>> BDC", body, "EMC")

    def grid(self, cols, rows, top=None, bottom=46, gap=10, heights=None):
        top = top if top is not None else H - 100
        w = (W - 2 * MARGIN - gap * (cols - 1)) / cols
        if heights is None:
            h = (top - bottom - gap * (rows - 1)) / rows
            heights = [h] * rows
        rects, y = [], top
        for r in range(rows):
            y -= heights[r]
            for c in range(cols):
                rects.append((MARGIN + c * (w + gap), y, w, heights[r]))
            y -= gap
        return rects

    def tile(self, rect, title, clause, expect, note=None, cover=None):
        x, y, w, h = rect
        self.doc.coverage.append(dict(object=cover or title, ref=clause, page=self.number, expect=expect,
                                      rect=(x, y, w, h)))
        if clause.startswith("T"):
            clause = "ISO 32000-2 " + clause.replace("T", "Table ", 1)
        self.artifact("q %s %s 0.6 w %s B Q" % (self.fill("tile"), self.stroke("rule"),
                                                round_rect_path(x, y, w, h, 4)))
        chip = {"swaps": "swaps", "stays": "stays", "viewer": "viewer"}[expect]
        f = self.doc.fonts.get("SansBold")
        cw = f.width(chip, 5.5) + 8
        size = 7.5
        while f.width(title, size) > w - cw - 20 and size > 5.2:
            size -= 0.25
        self.text(x + 7, y + h - 13, title, size=size, font="SansBold", tag="H2")
        csize = 5.8
        while self.doc.fonts.get("Sans").width(clause, csize) > w - 14 and csize > 4:
            csize -= 0.2
        self.text(x + 7, y + h - 22, clause, size=csize, role="muted")
        cx = x + w - cw - 6
        self.artifact("q %s %s f Q" % (self.fill(expect), round_rect_path(cx, y + h - 15, cw, 9, 4.5)))
        self.text(cx + 4, y + h - 12.2, chip, size=5.5, font="SansBold", role="paper", tag="Span")
        inner = (x + 7, y + 7 + (10 if note else 0), w - 14, h - 34 - (10 if note else 0))
        if note:
            self.text(x + 7, y + 6, note, size=5.6, role="muted")
        return inner

    def figure(self, body, alt):
        return self.tagged("Figure", body, alt=alt)

    # -- annotations ---------------------------------------------------------------
    def annot(self, d, tag=None, alt=None):
        d.P = self.obj
        a = self.pdf.make_indirect(d)
        self.annots.append(a)
        if tag:
            el = StructElem(tag, page=self, alt=alt)
            el.objr = a
            self.stack[-1].children.append(el)
        return a

    def finish(self):
        self.footer()
        content = "\n".join(self.ops) + "\n"
        self.obj.Contents = self.pdf.make_stream(content.encode("latin-1"))
        res = Dictionary()
        for cat, entries in self.res.items():
            if entries:
                res[Name("/" + cat)] = Dictionary({("/" + k): v for k, v in entries.items()})
        self.obj.Resources = res
        if self.annots:
            self.obj.Annots = Array(self.annots)
        for k, v in self.opts.items():
            self.obj[Name("/" + k)] = v


class Doc:
    def __init__(self, pal):
        self.pal = pal
        self.pdf = pikepdf.new()
        self.fonts = FontSet(self.pdf)
        self.pages = []
        self.shared = {}
        self.struct_root = StructElem("Document")
        self.fields = []
        self.outline = []          # (title, page_index, role, flags, children)
        self.named_dests = {}
        self.embedded = {}
        self.doc_js = {}
        self.ocgs = {}
        self.oc_config = None
        self.catalog_extra = {}
        self.page_labels = []
        self.threads = []
        self.acroform_extra = {}
        self.renditions = {}
        self.coverage = []
        self.thread_rects = []
        self.gotodp_links = []
        self.want_dparts = False
        self.appendix_start = None
        self.namespaces = {}

    def namespace(self, uri):
        if uri not in self.namespaces:
            self.namespaces[uri] = self.pdf.make_indirect(Dictionary(Type=Name.Namespace, NS=String(uri)))
        return self.namespaces[uri]

    def cover(self, obj, ref, page, expect):
        self.coverage.append(dict(object=obj, ref=ref, page=page, expect=expect))

    def once(self, key, make):
        if key not in self.shared:
            self.shared[key] = make()
        return self.shared[key]

    def stream(self, data, **entries):
        s = pikepdf.Stream(self.pdf, data if isinstance(data, bytes) else data.encode("latin-1"))
        for k, v in entries.items():
            s[Name("/" + k)] = v
        return s

    def form(self, body, bbox, resources=None, **entries):
        s = self.stream(body, Type=Name.XObject, Subtype=Name.Form, BBox=Array([float(v) for v in bbox]))
        if resources is not None:
            s.Resources = resources
        for k, v in entries.items():
            s[Name("/" + k)] = v
        return s

    def rgb(self, role):
        return Array([round(v, 4) for v in self.pal.rgb(role)])

    def embed_file(self, name, data, mime, desc=None, rel=None):
        if name in self.embedded:
            return self.embedded[name]
        ef = self.stream(data, Type=Name.EmbeddedFile, Subtype=Name("/" + mime.replace("/", "#2F")))
        ef.Params = Dictionary(Size=len(data), CreationDate=String("D:20261003120000Z"),
                               ModDate=String("D:20261003120000Z"))
        fs = Dictionary(Type=Name.Filespec, F=String(name), UF=String(name), EF=Dictionary(F=ef, UF=ef))
        if desc:
            fs.Desc = String(desc)
        if rel:
            fs.AFRelationship = Name("/" + rel)
        fs = self.pdf.make_indirect(fs)
        self.embedded[name] = fs
        return fs

    # -- structure tree --------------------------------------------------------------
    def _build_struct(self):
        pdf = self.pdf
        root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot))
        parent_nums = {}
        next_key = 0
        page_key = {}
        for p in self.pages:
            page_key[id(p)] = next_key
            p.obj.StructParents = next_key
            parent_nums[next_key] = [None] * len(p.mcid_elems)
            next_key += 1

        def build(el, parent_obj):
            d = Dictionary(Type=Name.StructElem, S=Name("/" + el.tag), P=parent_obj)
            if el.alt:
                d.Alt = String(el.alt)
            if el.title:
                d.T = String(el.title)
            if el.actual:
                d.ActualText = String(el.actual)
            if el.lang:
                d.Lang = String(el.lang)
            if el.attrs is not None:
                d.A = el.attrs
            if el.cls:
                d.C = Name("/" + el.cls)
            if el.ns is not None:
                d.NS = el.ns
            if el.expansion:
                d.E = String(el.expansion)
            if el.sid:
                d.ID = String(el.sid)
            if getattr(el, "af", None) is not None:
                d.AF = Array([el.af])
            obj = pdf.make_indirect(d)
            el.obj = obj
            kids = Array()
            if el.mcid is not None:
                obj.Pg = el.page.obj
                kids.append(el.mcid)
                parent_nums[page_key[id(el.page)]][el.mcid] = obj
            if el.objr is not None:
                nonlocal next_key
                obj.Pg = el.page.obj
                kids.append(Dictionary(Type=Name.OBJR, Obj=el.objr, Pg=el.page.obj))
                el.objr.StructParent = next_key
                parent_nums[next_key] = obj
                next_key += 1
            for c in el.children:
                kids.append(build(c, obj))
            if len(kids):
                obj.K = kids if len(kids) > 1 else kids[0]
            return obj

        doc_el = build(self.struct_root, root)
        root.K = doc_el
        nums = Array()
        for k in sorted(parent_nums):
            v = parent_nums[k]
            nums.append(k)
            nums.append(Array([x if x is not None else pikepdf.Object.parse(b"null") for x in v])
                        if isinstance(v, list) else v)
        root.ParentTree = pdf.make_indirect(Dictionary(Nums=nums))
        root.ParentTreeNextKey = next_key
        root.RoleMap = Dictionary(Note=Name.P, Swatch=Name.Figure)
        root.ClassMap = self.catalog_extra.pop("ClassMap", Dictionary())
        if self.namespaces:
            root.Namespaces = Array(list(self.namespaces.values()))
        return root

    def _outlines(self):
        pdf = self.pdf
        roles = ["ink", "accent", "red", "green", "purple", "teal", "orange", "blue"]
        root = pdf.make_indirect(Dictionary(Type=Name.Outlines))
        items = []
        for i, p in enumerate(self.pages):
            title = p.title or ("UserUnit page" if p.obj.get("/UserUnit") else "Page %d" % p.number)
            it = pdf.make_indirect(Dictionary(Title=String("%d  %s" % (p.number, title)), Parent=root,
                                              Dest=Array([p.obj, Name.Fit]), C=self.rgb(roles[i % len(roles)]),
                                              F=i % 4))
            kids = [c for c in self.coverage if c["page"] == p.number and c.get("rect")]
            if kids and not title.startswith("Appendix"):
                subs = []
                for c in kids:
                    x, y, w, h = c["rect"]
                    subs.append(pdf.make_indirect(Dictionary(Title=String(c["object"]), Parent=it,
                                                             Dest=Array([p.obj, Name.XYZ, x, y + h, 0]),
                                                             C=self.rgb(c["expect"]))))
                for a, b in zip(subs, subs[1:]):
                    a.Next, b.Prev = b, a
                it.First, it.Last, it.Count = subs[0], subs[-1], -len(subs)
            items.append(it)
        for a, b in zip(items, items[1:]):
            a.Next, b.Prev = b, a
        root.First, root.Last, root.Count = items[0], items[-1], len(items)
        return root

    def _threads(self):
        if not self.thread_rects:
            return
        pdf = self.pdf
        thread = pdf.make_indirect(Dictionary(Type=Name.Thread, I=Dictionary(Title=String("A test article"),
                                                                              Author=String("pdf-themes"))))
        beads = []
        for p, rect in self.thread_rects:
            b = pdf.make_indirect(Dictionary(Type=Name.Bead, P=p.obj, R=Array(rect)))
            beads.append(b)
            if Name.B not in p.obj:
                p.obj.B = Array()
            p.obj.B.append(b)
        for i, b in enumerate(beads):
            b.N = beads[(i + 1) % len(beads)]
            b.V = beads[i - 1]
        beads[0].T = thread
        thread.F = beads[0]
        pdf.Root.Threads = Array([thread])

    def _dparts(self):
        if not self.want_dparts or self.appendix_start is None:
            return
        pdf = self.pdf
        root_node = pdf.make_indirect(Dictionary(Type=Name.DPart))
        parts = []
        for name, a, b in [("Content", 0, self.appendix_start - 1), ("Appendix", self.appendix_start, len(self.pages) - 1)]:
            dp = pdf.make_indirect(Dictionary(Type=Name.DPart, Parent=root_node, Start=self.pages[a].obj,
                                              End=self.pages[b].obj,
                                              DPM=Dictionary(Name=String(name))))
            for p in self.pages[a:b + 1]:
                p.obj.DPart = dp
            parts.append(dp)
        root_node.DParts = Array([Array(parts)])
        dproot = pdf.make_indirect(Dictionary(Type=Name.DPartRoot, DPartRootNode=root_node,
                                              NodeNameList=Array([Name.Document, Name.Part])))
        root_node.Parent = dproot
        pdf.Root.DPartRoot = dproot
        for a in self.gotodp_links:
            a.A.Dp = parts[1]

    def finish(self):
        pdf = self.pdf
        for p in self.pages:
            p.finish()
        pdf.Root.Outlines = self._outlines()
        self._threads()
        self._dparts()
        if self.appendix_start is not None:
            pdf.Root.PageLabels = Dictionary(Nums=Array([0, Dictionary(S=Name.D),
                                                         self.appendix_start, Dictionary(S=Name.D, P=String("A-"))]))
        pdf.Root.StructTreeRoot = self._build_struct()
        pdf.Root.MarkInfo = Dictionary(Marked=True)
        pdf.Root.Lang = String("en-GB")
        pdf.Root.ViewerPreferences = Dictionary(DisplayDocTitle=True)
        pdf.Root.PageMode = Name.UseOutlines
        if self.fields or self.acroform_extra:
            dr = Dictionary(Font=Dictionary(Helv=self.fonts.standard("Helvetica").obj,
                                            ZaDb=self.fonts.standard("ZapfDingbats").obj))
            af = Dictionary(Fields=Array(self.fields), DR=dr, DA=String("/Helv 0 Tf 0 g"))
            for k, v in self.acroform_extra.items():
                if k[0].isupper():
                    af[Name("/" + k)] = v
            pdf.Root.AcroForm = af
        names = Dictionary()
        for key, table, wrap in (("Dests", self.named_dests, None), ("EmbeddedFiles", self.embedded, None),
                                 ("JavaScript", self.doc_js, "js")):
            if table:
                arr = Array()
                for k in sorted(table):
                    arr.append(String(k))
                    v = table[k]
                    arr.append(Dictionary(S=Name.JavaScript, JS=String(v)) if wrap == "js" else v)
                names[Name("/" + key)] = Dictionary(Names=arr)
        if len(names):
            pdf.Root.Names = names
        af = [fs for fs in self.embedded.values() if Name.AFRelationship in fs]
        if af:
            pdf.Root.AF = Array(af)
        if self.pages:
            pdf.Root.OpenAction = Array([self.pages[0].obj, Name.Fit])
        if self.ocgs:
            cfg = self.oc_config or {}
            D = Dictionary(Name=String("Default"), BaseState=Name.ON, ListMode=Name.AllPages,
                           ON=Array(cfg.get("on", [])), OFF=Array(cfg.get("off", [])),
                           Order=Array(cfg.get("order", list(self.ocgs.values()))),
                           RBGroups=Array([Array(g) for g in cfg.get("rbgroups", [])]),
                           Locked=Array(cfg.get("locked", [])))
            auto = cfg.get("auto", [])
            if auto:
                D.AS = Array([Dictionary(Event=ev, OCGs=Array(o), Category=Array(c)) for ev, o, c in auto])
            alt = Dictionary(Name=String("Everything on"), BaseState=Name.ON, Intent=Name.View,
                             Creator=String("pdf-themes objects test"))
            pdf.Root.OCProperties = Dictionary(OCGs=Array(list(self.ocgs.values())), D=D, Configs=Array([alt]))
        for k, v in self.catalog_extra.items():
            pdf.Root[Name("/" + k)] = v
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["dc:title"] = "PDF objects test for colour themes"
            meta["dc:creator"] = ["pdf-themes"]
            meta["dc:description"] = ("Every kind of object a PDF can hold and a viewer can show, "
                                      "built in a light and a dark design from one source.")
            meta["pdf:Producer"] = "pdf-themes objects test (pikepdf)"
        pdf.docinfo[Name.Title] = String("PDF objects test for colour themes")
        pdf.docinfo[Name.Producer] = String("pdf-themes objects test (pikepdf)")
        return pdf
