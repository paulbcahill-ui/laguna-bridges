"""Build exports/Bridge_Rails_BC_approval.pdf: summary + approval page, 3D preview, A3 fabrication sheet."""
import os, subprocess, textwrap
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages
here = os.path.dirname(os.path.abspath(__file__)); ex = os.path.join(here, "..", "exports")
p1 = os.path.join(ex, "_p1.pdf"); out = os.path.join(ex, "Bridge_Rails_BC_approval.pdf")
A4 = (8.27, 11.69)
with PdfPages(p1) as pdf:
    f = plt.figure(figsize=A4); f.text(0.08, 0.94, "Laguna Quays: Bridge Timber Rail Inserts", fontsize=17, weight="bold")
    f.text(0.08, 0.915, "For Body Corporate approval  |  Attention: Christine, Chairperson  |  From: Paul Cahill  |  5 November 2026", fontsize=8.5, color="#444")
    y = 0.875
    secs = [
     ("Purpose", "Replace the timber inserts in the gaps between the rock walls on both estate bridges. The rails are raised clear of the deck so storm water can pass underneath."),
     ("What is proposed", "Bridge 1: 4 rails, each 2150 mm long (two per side).\nBridge 2: 2 rails, each 3600 mm long (one per side).\nTimber section 300 mm wide x 200 mm high, laid flat. Rails sit 175 mm above the deck, with the top at 375 mm, just below the 400 mm rock walls. There is a 100 mm gap to the rock wall at each end."),
     ("Materials and fixing", "Durable Class 1 hardwood (e.g. spotted gum) or H4 treated timber, with chamfered top edges. Each rail sits on 2 hot-dip galvanised steel brackets bolted to the deck with M12 chemical anchors, and is fixed with M12 galvanised bolts. 12 brackets in total."),
     ("Points for confirmation", "1. The brief gave the timber as 300 high x 200 wide; laid that way the top would be 475 mm, above the walls, so the drawings show it laid flat (200 high).\n2. Bracket fixing is proposed; the carpenter or installer may substitute an equivalent.\n3. The carpenter is to check opening lengths on site before cutting."),
     ("Attached", "Page 2: 3D view of both bridges.\nPage 3: A3 fabrication drawing (plan, elevation, rail section, cut list)."),
    ]
    for h, body in secs:
        f.text(0.08, y, h, fontsize=11, weight="bold"); y -= 0.025
        for para in body.split("\n"):
            for line in textwrap.wrap(para, 95):
                f.text(0.08, y, line, fontsize=9.5); y -= 0.019
        y -= 0.015
    f.text(0.08, y - 0.01, "Body Corporate approval", fontsize=11, weight="bold"); y -= 0.06
    for lab in ["Approved  /  Approved with changes  /  Not approved", "Comments:", "", "Name:", "Signature:", "Date:"]:
        f.text(0.08, y, lab, fontsize=9.5)
        if lab and lab[0] != "A": f.add_artist(plt.Line2D([0.22, 0.9], [y - 0.003, y - 0.003], lw=0.6, color="#666"))
        if lab == "": f.add_artist(plt.Line2D([0.08, 0.9], [y - 0.003, y - 0.003], lw=0.6, color="#666"))
        y -= 0.04
    pdf.savefig(f); plt.close(f)
    f = plt.figure(figsize=(11.69, 8.27)); ax = f.add_axes([0.02, 0.02, 0.96, 0.92]); ax.imshow(mpimg.imread(os.path.join(ex, "Bridge_Rails_iso.png"))); ax.axis("off")
    pdf.savefig(f); plt.close(f)
subprocess.check_call(["pdfunite", p1, os.path.join(ex, "Bridge_Rails_fabrication.pdf"), out]); os.remove(p1); print("SAVED", out)
