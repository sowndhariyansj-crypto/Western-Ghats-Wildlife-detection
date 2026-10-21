import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

os.makedirs('results/report_assets', exist_ok=True)

# ----------------------------------------------------------------------
# Helper styles
# ----------------------------------------------------------------------
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'

# 1. Figure 4.1: Multi-Tiered Architecture Schematic
def create_fig_4_1():
    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    tiers = [
        ("Tier 1: Field Sensing & Camera Trap Ingestion", 
         ["Forest Camera Traps", "Field Ranger Mobile Uploads", "Aerial Wildlife Feeds", "iNaturalist Research Repository"], 
         8.0, "#e0f2fe", "#0284c7"),
        ("Tier 2: Ingestion, Validation & Preprocessing Pipeline", 
         ["MD5 Hash Deduplication", "YOLO Normalization ([0,1])", "HSV Color Jitter & Scaling", "Mosaic & MixUp Scheduling"], 
         6.0, "#f0fdf4", "#16a34a"),
        ("Tier 3: Deep Neural Network Detection Engine", 
         ["YOLOv8s Pretrained Backbone", "Cross Stage Partial (C2f) Blocks", "Spatial Pyramid Pooling (SPPF)", "Decoupled Anchor-Free Detection Head"], 
         4.0, "#fef3c7", "#d97706"),
        ("Tier 4: Conservation Intelligence & Analytics Layer", 
         ["IUCN Red List Status Registry", "Western Ghats Habitat Range Mapping", "Non-Maximum Suppression (IoU 0.45)", "Confidence Thresholding Engine"], 
         2.0, "#f3e8ff", "#9333ea"),
        ("Tier 5: Presentation & Actionable Reporting Portal", 
         ["Streamlit Real-Time Dashboard", "OpenCV Frame-by-Frame Video Tracking", "CSV / JSON Analytical Exports", "Multi-Species Conservation Cards"], 
         0.0, "#ffe4e6", "#e11d48"),
    ]

    for title, items, y, bg_color, border_color in tiers:
        rect = patches.FancyBboxPatch((0.5, y + 0.1), 9.0, 1.6, boxstyle="round,pad=0.1",
                                      facecolor=bg_color, edgecolor=border_color, linewidth=1.8)
        ax.add_patch(rect)
        ax.text(5.0, y + 1.4, title, ha='center', va='center', fontsize=11, fontweight='bold', color='#0f172a')
        
        # Draw items inside
        for i, item in enumerate(items):
            box_x = 0.8 + i * 2.15
            sub_rect = patches.FancyBboxPatch((box_x, y + 0.3), 2.0, 0.8, boxstyle="round,pad=0.05",
                                              facecolor="#ffffff", edgecolor=border_color, linewidth=1.0)
            ax.add_patch(sub_rect)
            ax.text(box_x + 1.0, y + 0.7, item, ha='center', va='center', fontsize=7.5, fontweight='semibold', color='#1e293b', wrap=True)

        if y > 0:
            ax.annotate('', xy=(5.0, y), xytext=(5.0, y + 0.1),
                        arrowprops=dict(facecolor='#475569', edgecolor='#475569', arrowstyle="->", lw=2.0))

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_1_architecture.png', bbox_inches='tight')
    plt.close()

# 2. Figure 4.3: End-to-End Workflow Flowchart
def create_fig_4_3():
    fig, ax = plt.subplots(figsize=(8, 10), dpi=300)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 11)
    ax.axis('off')

    steps = [
        ("Step 1: Input Acquisition", "Ranger uploads photo / video stream or stages camera trap batch", 10.0, "#e2e8f0"),
        ("Step 2: Integrity & Coordinate Validation", "Check image format, MD5 hash uniqueness, bounding box bounds [0, 1]", 8.8, "#bfdbfe"),
        ("Step 3: Preprocessing & Resize", "Resize to 640x640 letterbox, normalize pixel intensity to [0, 1]", 7.6, "#bbf7d0"),
        ("Step 4: YOLOv8s Forward Inference", "Extract spatial features via CSPDarknet & C2f, compute multi-scale maps", 6.4, "#fed7aa"),
        ("Step 5: Post-Processing & NMS", "Filter overlapping candidate boxes using Non-Maximum Suppression (IoU 0.45)", 5.2, "#fef08a"),
        ("Step 6: Confidence Thresholding", "Retain detections exceeding confidence threshold (default 25%)", 4.0, "#e9d5ff"),
        ("Step 7: IUCN Taxonomic Enrichment", "Map class ID to scientific name, conservation status (EN, VU, CR), and habitat", 2.8, "#fecdd3"),
        ("Step 8: Visualization & Export", "Render bounding boxes with status tags, display species cards, export CSV/JSON", 1.6, "#c7d2fe"),
    ]

    for title, desc, y, color in steps:
        rect = patches.FancyBboxPatch((1.0, y - 0.4), 6.0, 0.9, boxstyle="round,pad=0.1",
                                      facecolor=color, edgecolor="#334155", linewidth=1.5)
        ax.add_patch(rect)
        ax.text(4.0, y + 0.25, title, ha='center', va='center', fontsize=9.5, fontweight='bold', color='#0f172a')
        ax.text(4.0, y - 0.1, desc, ha='center', va='center', fontsize=7.5, color='#334155')
        
        if y > 1.6:
            ax.annotate('', xy=(4.0, y - 0.4), xytext=(4.0, y - 0.65),
                        arrowprops=dict(facecolor='#0f172a', edgecolor='#0f172a', arrowstyle="<-", lw=1.8))

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_3_workflow.png', bbox_inches='tight')
    plt.close()

# 3. Figure 4.4: YOLOv8 Architecture
def create_fig_4_4():
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    modules = [
        ("Input", "Image\n(640x640x3)", 0.5, 2.5, 1.2, 1.2, "#e2e8f0"),
        ("Backbone", "CSPDarknet\n- Conv (k=3, s=2)\n- C2f Modules\n- SPPF Layer", 2.2, 2.0, 2.2, 2.2, "#bfdbfe"),
        ("Neck", "PANet Feature Pyramid\n- Multi-Scale Concatenation\n- UpSampling & C2f\n- P3, P4, P5 Scales", 4.8, 2.0, 2.3, 2.2, "#bbf7d0"),
        ("Decoupled Head", "Anchor-Free Heads\n- Class Branch (BCE)\n- Box Branch (CIoU + DFL)\n- Multi-Scale Output", 7.5, 2.0, 2.2, 2.2, "#fed7aa"),
    ]

    for label, text, x, y, w, h, col in modules:
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                                      facecolor=col, edgecolor="#1e293b", linewidth=1.6)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h + 0.3, label, ha='center', va='center', fontsize=11, fontweight='bold', color='#0f172a')
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=8.5, color='#0f172a')

    # Connect with arrows
    ax.annotate('', xy=(2.2, 3.1), xytext=(1.7, 3.1), arrowprops=dict(facecolor='#1e293b', arrowstyle="->", lw=2))
    ax.annotate('', xy=(4.8, 3.1), xytext=(4.4, 3.1), arrowprops=dict(facecolor='#1e293b', arrowstyle="->", lw=2))
    ax.annotate('', xy=(7.5, 3.1), xytext=(7.1, 3.1), arrowprops=dict(facecolor='#1e293b', arrowstyle="->", lw=2))

    # Loss Functions box below
    loss_rect = patches.FancyBboxPatch((1.5, 0.4), 7.0, 1.0, boxstyle="round,pad=0.08",
                                       facecolor="#fef3c7", edgecolor="#d97706", linewidth=1.5)
    ax.add_patch(loss_rect)
    ax.text(5.0, 1.05, "Objective Optimization Losses", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#92400e')
    ax.text(5.0, 0.65, "Total Loss = λ_box * L_CIoU + λ_cls * L_BCE + λ_dfl * L_DFL", ha='center', va='center', fontsize=9, color='#78350f', family='monospace')

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_4_yolov8.png', bbox_inches='tight')
    plt.close()

# 4. Figure 4.5: Use Case Diagram
def create_fig_4_5():
    fig, ax = plt.subplots(figsize=(9, 7), dpi=300)
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Boundary
    boundary = patches.FancyBboxPatch((2.2, 0.4), 6.4, 7.2, boxstyle="round,pad=0.1",
                                      facecolor="#f8fafc", edgecolor="#475569", linewidth=2.0)
    ax.add_patch(boundary)
    ax.text(5.4, 7.3, "Western Ghats Wildlife Monitoring Platform", ha='center', va='center', fontsize=11, fontweight='bold')

    usecases = [
        ("Upload Field Image & Run Inference", 6.4),
        ("Upload Video & Frame-by-Frame Tracking", 5.4),
        ("Adjust Confidence & NMS Thresholds", 4.4),
        ("Inspect IUCN Red List Species Profiles", 3.4),
        ("Export CSV / JSON Detection Records", 2.4),
        ("Ingest New Photos & Retrain Model", 1.4),
    ]

    for uc_text, y in usecases:
        ellipse = patches.Ellipse((5.4, y), 5.2, 0.65, facecolor="#ffffff", edgecolor="#0284c7", linewidth=1.5)
        ax.add_patch(ellipse)
        ax.text(5.4, y, uc_text, ha='center', va='center', fontsize=8.5, color='#0f172a')

    # Actors
    actors = [
        ("Forest Ranger", 1.0, 5.5),
        ("Field Biologist", 1.0, 3.5),
        ("System Admin", 1.0, 1.5)
    ]
    for name, ax_pos, ay_pos in actors:
        # draw stick figure circle and lines
        ax.plot([ax_pos], [ay_pos + 0.3], marker='o', markersize=14, color='#1e293b')
        ax.plot([ax_pos, ax_pos], [ay_pos + 0.15, ay_pos - 0.25], color='#1e293b', lw=2)
        ax.plot([ax_pos - 0.25, ax_pos + 0.25], [ay_pos, ay_pos], color='#1e293b', lw=2)
        ax.plot([ax_pos, ax_pos - 0.25], [ay_pos - 0.25, ay_pos - 0.55], color='#1e293b', lw=2)
        ax.plot([ax_pos, ax_pos + 0.25], [ay_pos - 0.25, ay_pos - 0.55], color='#1e293b', lw=2)
        ax.text(ax_pos, ay_pos - 0.75, name, ha='center', va='center', fontsize=8.5, fontweight='bold')

    # Connect lines
    for _, _, ay in actors:
        for _, uy in usecases:
            if abs(ay - uy) < 2.5:
                ax.plot([1.2, 2.8], [ay, uy], color='#94a3b8', linestyle='--', lw=1.0)

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_5_usecase.png', bbox_inches='tight')
    plt.close()

# 5. Figure 4.6: DFD Level 0
def create_fig_4_6():
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 5)
    ax.axis('off')

    # External entities
    ent1 = patches.Rectangle((0.4, 2.8), 2.2, 1.4, facecolor="#e2e8f0", edgecolor="#1e293b", linewidth=1.5)
    ax.add_patch(ent1)
    ax.text(1.5, 3.5, "Field Ranger /\nCamera Trap", ha='center', va='center', fontsize=9.5, fontweight='bold')

    ent2 = patches.Rectangle((0.4, 0.6), 2.2, 1.4, facecolor="#e2e8f0", edgecolor="#1e293b", linewidth=1.5)
    ax.add_patch(ent2)
    ax.text(1.5, 1.3, "Conservation\nAuthority / Admin", ha='center', va='center', fontsize=9.5, fontweight='bold')

    # Process
    proc = patches.Circle((5.6, 2.5), 1.6, facecolor="#dbeafe", edgecolor="#1d4ed8", linewidth=2.0)
    ax.add_patch(proc)
    ax.text(5.6, 2.7, "0.0\nWestern Ghats\nWildlife AI", ha='center', va='center', fontsize=10, fontweight='bold', color='#1e3a8a')
    ax.text(5.6, 1.8, "Detection System", ha='center', va='center', fontsize=9, fontweight='semibold', color='#1e3a8a')

    # Arrows
    ax.annotate('Field Image/Video, Settings', xy=(4.0, 3.2), xytext=(2.6, 3.6),
                arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5), fontsize=8)
    ax.annotate('Bounding Boxes, IUCN Cards', xy=(2.6, 3.1), xytext=(4.1, 2.7),
                arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5), fontsize=8)

    ax.annotate('Batch Images & Annotations', xy=(4.1, 2.0), xytext=(2.6, 1.6),
                arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5), fontsize=8)
    ax.annotate('Audit Logs, Model Status', xy=(2.6, 1.0), xytext=(4.2, 1.3),
                arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5), fontsize=8)

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_6_dfd0.png', bbox_inches='tight')
    plt.close()

# 6. Figure 4.7: DFD Level 1
def create_fig_4_7():
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    procs = [
        ("1.0 Ingestion &\nValidation", 1.8, 4.5),
        ("2.0 Preprocessing\n& Augmentation", 4.2, 4.5),
        ("3.0 YOLOv8s Feature\nExtraction", 6.8, 4.5),
        ("4.0 NMS & Score\nThresholding", 8.2, 2.2),
        ("5.0 IUCN Taxonomic\nEnrichment", 5.2, 2.2),
        ("6.0 Visualization\n& Export", 2.2, 2.2),
    ]

    for name, x, y in procs:
        circ = patches.Circle((x, y), 0.75, facecolor="#eff6ff", edgecolor="#2563eb", linewidth=1.5)
        ax.add_patch(circ)
        ax.text(x, y, name, ha='center', va='center', fontsize=7.5, fontweight='bold', color='#1e3a8a')

    # Data Stores
    ax.text(5.5, 5.7, "[D1] YOLO Dataset YAML & Images", fontsize=8.5, fontweight='bold', family='monospace', bbox=dict(facecolor='#f1f5f9', edgecolor='#64748b'))
    ax.text(5.5, 0.6, "[D2] Trained YOLOv8 Checkpoint (best.pt)", fontsize=8.5, fontweight='bold', family='monospace', bbox=dict(facecolor='#f1f5f9', edgecolor='#64748b'))
    ax.text(1.2, 0.6, "[D3] IUCN Species Metadata", fontsize=8.5, fontweight='bold', family='monospace', bbox=dict(facecolor='#f1f5f9', edgecolor='#64748b'))

    # Connect
    ax.annotate('', xy=(3.45, 4.5), xytext=(2.55, 4.5), arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5))
    ax.annotate('', xy=(6.05, 4.5), xytext=(4.95, 4.5), arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5))
    ax.annotate('', xy=(8.2, 2.95), xytext=(7.2, 3.8), arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5))
    ax.annotate('', xy=(5.95, 2.2), xytext=(7.45, 2.2), arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5))
    ax.annotate('', xy=(2.95, 2.2), xytext=(4.45, 2.2), arrowprops=dict(facecolor='#0f172a', arrowstyle="->", lw=1.5))

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_7_dfd1.png', bbox_inches='tight')
    plt.close()

# 7. Figure 4.8: Sequence Diagram
def create_fig_4_8():
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 7)
    ax.axis('off')

    lifelines = [
        ("Field Ranger", 1.0),
        ("Streamlit UI", 3.0),
        ("Inference Controller", 5.0),
        ("YOLOv8 Engine", 7.0),
        ("Species Registry", 8.5)
    ]

    for name, x in lifelines:
        box = patches.Rectangle((x - 0.7, 6.2), 1.4, 0.6, facecolor="#f1f5f9", edgecolor="#334155", linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, 6.5, name, ha='center', va='center', fontsize=8, fontweight='bold')
        ax.plot([x, x], [6.2, 0.5], color='#94a3b8', linestyle='--', lw=1.2)

    messages = [
        (1, 1.0, 3.0, 5.6, "1: Upload Photo / Video"),
        (2, 3.0, 5.0, 4.8, "2: parse_input(image_bytes, conf)"),
        (3, 5.0, 7.0, 4.0, "3: model.predict(imgsz=640, conf=0.25)"),
        (4, 7.0, 5.0, 3.2, "4: Return Boxes, ClassIDs, Confidences"),
        (5, 5.0, 8.5, 2.4, "5: lookup_iucn_status(class_name)"),
        (6, 8.5, 5.0, 1.8, "6: Return Scientific Name, Range, Status"),
        (7, 5.0, 3.0, 1.2, "7: Annotated BGR Image + Detection Dictionaries"),
        (8, 3.0, 1.0, 0.7, "8: Render Bounding Boxes & IUCN Cards"),
    ]

    for step, x1, x2, y, txt in messages:
        ax.annotate(txt, xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(facecolor='#0f172a', edgecolor='#0f172a', arrowstyle="->", lw=1.3),
                    fontsize=7.5, va='bottom')

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_8_sequence.png', bbox_inches='tight')
    plt.close()

# 8. Figure 4.9: Relational Schema & Annotation Format
def create_fig_4_9():
    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    ax.set_xlim(0, 9)
    ax.set_ylim(0, 5)
    ax.axis('off')

    # Left: YOLO Bounding Box Structure
    b1 = patches.FancyBboxPatch((0.5, 1.2), 3.8, 3.2, boxstyle="round,pad=0.1",
                                facecolor="#eff6ff", edgecolor="#3b82f6", linewidth=1.5)
    ax.add_patch(b1)
    ax.text(2.4, 4.0, "YOLO Normalized Format (.txt)", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#1d4ed8')
    txt_yolo = (
        "<class_id> <x_center> <y_center> <width> <height>\n\n"
        "Coordinates normalized to [0.0, 1.0]:\n"
        "• x_center = X_box_center / Image_Width\n"
        "• y_center = Y_box_center / Image_Height\n"
        "• width    = Box_Width / Image_Width\n"
        "• height   = Box_Height / Image_Height\n\n"
        "Example:\n"
        "0 0.5124 0.4382 0.3120 0.4502"
    )
    ax.text(0.7, 2.5, txt_yolo, ha='left', va='center', fontsize=7.5, family='monospace', color='#1e293b')

    # Right: Metadata Schema
    b2 = patches.FancyBboxPatch((4.7, 1.2), 3.8, 3.2, boxstyle="round,pad=0.1",
                                facecolor="#f0fdf4", edgecolor="#22c55e", linewidth=1.5)
    ax.add_patch(b2)
    ax.text(6.6, 4.0, "Dataset Metadata Schema (.csv)", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#15803d')
    txt_meta = (
        "metadata.csv Attributes:\n"
        "• filename        : Unique image path\n"
        "• species         : Label ID [0-9]\n"
        "• scientific_name : Binomial nomenclature\n"
        "• source_site     : iNaturalist / Wikimedia\n"
        "• license         : CC-BY-4.0 / CC0\n"
        "• split           : train / val / test\n"
        "• iucn_code       : CR / EN / VU\n"
        "• region          : Western Ghats Reserve"
    )
    ax.text(4.9, 2.5, txt_meta, ha='left', va='center', fontsize=7.5, family='monospace', color='#1e293b')

    plt.tight_layout()
    plt.savefig('results/report_assets/fig_4_9_schema.png', bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    create_fig_4_1()
    create_fig_4_3()
    create_fig_4_4()
    create_fig_4_5()
    create_fig_4_6()
    create_fig_4_7()
    create_fig_4_8()
    create_fig_4_9()
    print("All diagrams created successfully!")
