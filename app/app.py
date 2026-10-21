# ============================================================
# app/app.py
# Streamlit Web Application — AI-Based Animal Detection
#
# Supports:
#   - Photo upload + inference
#   - Video upload + frame-by-frame processing
#   - Confidence threshold slider
#   - Model checkpoint selector
#   - Downloadable annotated images/videos and CSV/JSON results
#   - Clear mode indicators (Demo / Generic / Trained)
#   - Helpful messages when model or data is missing
#
# Run with:
#   streamlit run app/app.py
# ============================================================

from __future__ import annotations

import csv
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st

# ── Ensure project root is on sys.path ──────────────────────────
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (
    load_config,
    get_class_names,
    is_trained_model_available,
    get_model_checkpoint,
    get_species_info,
    get_project_metadata,
)
from src.inference import run_inference, draw_status_overlay

# ── Page config (must be first Streamlit call) ───────────────────
st.set_page_config(
    page_title="Western Ghats Wildlife Detector — Tamil Nadu & Kerala",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════
# Custom CSS — Dark Wildlife Theme
# ══════════════════════════════════════════════════════════════════
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400;1,600&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    /* ─── Global typography & dark theme resets ─── */
    html, body, [class*="css"], .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        color: #e2e8f0 !important;
        letter-spacing: -0.01em;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif !important;
        color: #f1f5f9 !important;
        letter-spacing: -0.025em !important;
    }

    /* ─── Dark background with ambient dark mesh ─── */
    .stApp {
        background-color: #0f172a;
        background-image:
            linear-gradient(rgba(16, 185, 129, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(16, 185, 129, 0.03) 1px, transparent 1px),
            radial-gradient(ellipse 120% 80% at 10% 5%,  rgba(16, 185, 129, 0.07) 0%, transparent 60%),
            radial-gradient(ellipse 90% 120% at 90% 90%, rgba(14, 165, 233, 0.06) 0%, transparent 60%),
            linear-gradient(160deg, #0f172a 0%, #0d1526 50%, #0f172a 100%);
        background-size: 36px 36px, 36px 36px, 100% 100%, 100% 100%, 100% 100%;
        color: #e2e8f0;
        min-height: 100vh;
        overflow-x: hidden;
    }

    /* ─── Ambient dark orbs ─── */
    .stApp::before {
        content: '';
        position: fixed;
        top: -15%; left: -8%;
        width: 500px; height: 500px;
        background: radial-gradient(circle, rgba(16, 185, 129, 0.07) 0%, transparent 70%);
        border-radius: 50%;
        animation: float-orb 20s ease-in-out infinite alternate;
        pointer-events: none;
        z-index: 0;
    }
    .stApp::after {
        content: '';
        position: fixed;
        bottom: -15%; right: -5%;
        width: 460px; height: 460px;
        background: radial-gradient(circle, rgba(2, 132, 199, 0.06) 0%, transparent 70%);
        border-radius: 50%;
        animation: float-orb 26s ease-in-out infinite alternate-reverse;
        pointer-events: none;
        z-index: 0;
    }
    @keyframes float-orb {
        from { transform: translate(0px, 0px) scale(1.0); }
        to   { transform: translate(50px, 35px) scale(1.12); }
    }

    /* ─── Sidebar — dark glass panel ─── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.97) 0%, rgba(13, 21, 38, 0.98) 100%) !important;
        border-right: 1px solid rgba(16, 185, 129, 0.15) !important;
        backdrop-filter: blur(20px) saturate(1.2);
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.3) !important;
    }
    section[data-testid="stSidebar"]::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, #10b981, #0284c7, transparent);
        pointer-events: none;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label {
        color: #94a3b8 !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] h2 { color: #10b981 !important; }
    section[data-testid="stSidebar"] h3 {
        color: #10b981 !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
    }
    /* Selectbox & input wrappers in sidebar */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"] {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2) !important;
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within {
        border-color: #059669 !important;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15) !important;
    }

    /* ─── Sidebar slider ─── */
    .stSlider [data-baseweb="slider"] [role="slider"] {
        background: #059669 !important;
        box-shadow: 0 2px 8px rgba(5, 150, 105, 0.45) !important;
        border: 2px solid #0f172a !important;
    }
    .stSlider [data-baseweb="slider"] > div > div {
        background: linear-gradient(90deg, #10b981, #0284c7) !important;
    }

    /* ─── HERO BANNER — dark showcase ─── */
    .hero-banner {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(20, 35, 25, 0.85) 45%, rgba(15, 25, 40, 0.80) 100%);
        border: 1px solid rgba(16, 185, 129, 0.25);
        border-radius: 20px;
        padding: 34px 40px 28px;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 40px -5px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(16, 185, 129, 0.08);
    }
    .hero-banner::before {
        content: '';
        position: absolute;
        top: 14px; left: 14px;
        width: 26px; height: 26px;
        border-top: 2.5px solid rgba(5, 150, 105, 0.75);
        border-left: 2.5px solid rgba(5, 150, 105, 0.75);
        border-radius: 2px 0 0 0;
        pointer-events: none;
    }
    .hero-banner::after {
        content: '';
        position: absolute;
        bottom: 14px; right: 14px;
        width: 26px; height: 26px;
        border-bottom: 2.5px solid rgba(2, 132, 199, 0.65);
        border-right: 2.5px solid rgba(2, 132, 199, 0.65);
        border-radius: 0 0 2px 0;
        pointer-events: none;
    }
    .hero-banner .scan-line {
        position: absolute;
        left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(5, 150, 105, 0.55) 50%, transparent 100%);
        animation: scan 4.5s ease-in-out infinite;
        pointer-events: none;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
    }
    @keyframes scan {
        0%   { top: 0%;   opacity: 0; }
        5%   { opacity: 1; }
        95%  { opacity: 1; }
        100% { top: 100%; opacity: 0; }
    }
    .hero-orb1 {
        position: absolute;
        top: -40px; right: 60px;
        width: 180px; height: 180px;
        background: radial-gradient(circle, rgba(16, 185, 129, 0.10) 0%, transparent 70%);
        border-radius: 50%;
        animation: orb-drift 12s ease-in-out infinite alternate;
        pointer-events: none;
    }
    .hero-orb2 {
        position: absolute;
        bottom: -30px; left: 40px;
        width: 140px; height: 140px;
        background: radial-gradient(circle, rgba(14, 165, 233, 0.08) 0%, transparent 70%);
        border-radius: 50%;
        animation: orb-drift 16s ease-in-out infinite alternate-reverse;
        pointer-events: none;
    }
    @keyframes orb-drift {
        from { transform: translate(0,0) scale(1); }
        to   { transform: translate(16px, 12px) scale(1.1); }
    }
    .hero-title {
        font-family: 'Outfit', sans-serif !important;
        font-size: 2.25rem !important;
        font-weight: 800 !important;
        background: linear-gradient(110deg, #34d399 0%, #10b981 32%, #38bdf8 75%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 8px;
        line-height: 1.18;
        letter-spacing: -0.025em;
        text-shadow: none;
    }
    .hero-sub {
        color: #94a3b8 !important;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: 0.06em;
        font-family: 'JetBrains Mono', monospace;
    }
    .hero-tags {
        margin-top: 18px;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }
    .hero-tag {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        color: #34d399;
        font-size: 0.70rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        padding: 5px 14px;
        border-radius: 20px;
        text-transform: uppercase;
        transition: all 0.2s cubic-bezier(.34,1.56,.64,1);
        cursor: default;
        font-family: 'JetBrains Mono', monospace;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
    }
    .hero-tag:hover {
        background: rgba(16, 185, 129, 0.18);
        border-color: #059669;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
        color: #6ee7b7;
        transform: translateY(-1px);
    }

    /* ─── Metric cards — dark glass cards ─── */
    .metric-card {
        background: linear-gradient(145deg, #1e293b 0%, #162032 100%);
        border: 1px solid rgba(51, 65, 85, 0.9);
        border-radius: 18px;
        padding: 24px 18px 20px;
        text-align: center;
        margin-bottom: 14px;
        box-shadow: 0 4px 18px -2px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.2);
        position: relative;
        overflow: hidden;
        transition: transform 0.3s cubic-bezier(.34,1.56,.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 10%; right: 10%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.4), rgba(2, 132, 199, 0.3), transparent);
    }
    .metric-card::after {
        content: '';
        position: absolute;
        bottom: 0; left: 50%;
        transform: translateX(-50%) scaleX(0);
        width: 50%; height: 2px;
        background: linear-gradient(90deg, #10b981, #0284c7);
        border-radius: 2px;
        transition: transform 0.3s cubic-bezier(.34,1.56,.64,1);
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.4);
    }
    .metric-card:hover {
        transform: translateY(-5px) scale(1.02);
        border-color: rgba(16, 185, 129, 0.35);
        box-shadow: 0 14px 34px -4px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(16, 185, 129, 0.1);
    }
    .metric-card:hover::after { transform: translateX(-50%) scaleX(1); }
    .metric-value {
        font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif !important;
        font-size: 2.7rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #34d399 0%, #38bdf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1.0;
        display: block;
        letter-spacing: -0.025em;
    }
    .metric-icon {
        font-size: 1.6rem;
        margin-bottom: 8px;
        display: block;
        filter: drop-shadow(0 2px 6px rgba(16, 185, 129, 0.35));
        animation: icon-pulse 3s ease-in-out infinite;
    }
    @keyframes icon-pulse {
        0%, 100% { transform: scale(1); }
        50%       { transform: scale(1.08); }
    }
    .metric-label {
        font-size: 0.69rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-top: 7px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-sep {
        width: 32px; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.35), transparent);
        margin: 6px auto 0;
    }

    /* ─── Status badges ─── */
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 5px 16px;
        border-radius: 30px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        font-family: 'JetBrains Mono', monospace;
        transition: all 0.2s ease;
    }
    .badge-generic {
        background: rgba(245, 158, 11, 0.12);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
        box-shadow: 0 1px 4px rgba(245, 158, 11, 0.1);
    }
    .badge-trained {
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
        box-shadow: 0 1px 4px rgba(16, 185, 129, 0.15);
        animation: badge-glow 2.5s ease-in-out infinite;
    }
    @keyframes badge-glow {
        0%, 100% { box-shadow: 0 1px 4px rgba(16, 185, 129, 0.15); }
        50%       { box-shadow: 0 3px 12px rgba(16, 185, 129, 0.3); }
    }
    .badge-demo    { background: rgba(139, 92, 246, 0.12); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-nomodel { background: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }

    /* ─── Notification boxes ─── */
    .info-box, .warning-box, .error-box, .success-box {
        border-radius: 14px;
        padding: 14px 20px;
        margin: 14px 0;
        font-size: 0.875rem;
        line-height: 1.65;
        position: relative;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .info-box::before, .warning-box::before,
    .error-box::before, .success-box::before {
        content: '';
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 4px;
        border-radius: 14px 0 0 14px;
    }
    .info-box    { background: rgba(2, 132, 199, 0.1); border: 1px solid rgba(2, 132, 199, 0.25); color: #7dd3fc; }
    .info-box::before    { background: #0284c7; }
    .warning-box { background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); color: #fcd34d; }
    .warning-box::before { background: #f59e0b; }
    .error-box   { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.25); color: #fca5a5; }
    .error-box::before   { background: #ef4444; }
    .success-box { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); color: #6ee7b7; }
    .success-box::before { background: #10b981; }

    /* ─── Mode banner ─── */
    .mode-banner {
        border-radius: 16px;
        padding: 14px 22px;
        margin: 0 0 24px;
        display: flex;
        align-items: center;
        gap: 16px;
        border: 1px solid;
        font-size: 0.86rem;
        line-height: 1.65;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .mode-banner.trained {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(5, 150, 105, 0.08) 100%);
        border-color: rgba(16, 185, 129, 0.3);
        color: #6ee7b7;
    }
    .mode-banner.generic {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(217, 119, 6, 0.08) 100%);
        border-color: rgba(245, 158, 11, 0.3);
        color: #fcd34d;
    }
    .mode-banner.nomodel {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(220, 38, 38, 0.08) 100%);
        border-color: rgba(239, 68, 68, 0.3);
        color: #fca5a5;
    }

    /* ─── Section headers ─── */
    .section-header {
        font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif !important;
        font-size: 1.02rem;
        font-weight: 700;
        color: #f1f5f9;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 0 10px 14px;
        margin: 24px 0 16px;
        border-left: 4px solid #059669;
        border-bottom: 1px solid #1e293b;
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.06), transparent);
        position: relative;
    }
    .section-header::after {
        content: '';
        position: absolute;
        left: 14px; bottom: 0;
        width: 40px; height: 1.5px;
        background: #059669;
    }

    /* ─── Detection table ─── */
    .det-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.84rem;
        border-radius: 12px;
        overflow: hidden;
        background: #1e293b;
        border: 1px solid #334155;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .det-table th {
        background: #162032;
        color: #94a3b8;
        padding: 12px 16px;
        text-align: left;
        font-weight: 700;
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-bottom: 2px solid #334155;
        font-family: 'JetBrains Mono', monospace;
    }
    .det-table td {
        padding: 11px 16px;
        border-bottom: 1px solid #253347;
        color: #cbd5e1;
        transition: background 0.18s ease, color 0.18s ease;
    }
    .det-table tr:hover td {
        background: rgba(16, 185, 129, 0.07);
        color: #6ee7b7;
    }
    .det-table tr:last-child td { border-bottom: none; }
    .det-table tbody tr:nth-child(even) td {
        background: rgba(15, 23, 42, 0.4);
    }

    /* ─── Confidence bar ─── */
    .conf-bar-bg {
        background: #334155;
        border-radius: 8px;
        height: 6px;
        width: 100%;
        margin-bottom: 4px;
        overflow: hidden;
    }
    .conf-bar-fill {
        height: 6px;
        border-radius: 8px;
        background: linear-gradient(90deg, #10b981 0%, #06b6d4 60%, #6366f1 100%);
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
    }

    /* ─── Species cards ─── */
    .species-card {
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 16px;
        border: 1px solid #334155;
        background: #1e293b;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        transition: transform 0.3s cubic-bezier(.34,1.56,.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .species-card:hover {
        transform: translateY(-4px) scale(1.01);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(16, 185, 129, 0.15);
        border-color: rgba(16, 185, 129, 0.3);
    }

    /* ─── Download buttons ─── */
    .stDownloadButton > button {
        background: #1e293b !important;
        color: #34d399 !important;
        border: 1.5px solid #059669 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 0.83rem !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        padding: 9px 20px !important;
        transition: all 0.25s ease !important;
        letter-spacing: 0.01em !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
    }
    .stDownloadButton > button:hover {
        border-color: #10b981 !important;
        box-shadow: 0 4px 14px rgba(5, 150, 105, 0.25) !important;
        transform: translateY(-2px) !important;
        background: rgba(16, 185, 129, 0.12) !important;
        color: #6ee7b7 !important;
    }

    /* ─── Primary action buttons ─── */
    .stButton > button {
        background: linear-gradient(135deg, #059669 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 11px !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        padding: 11px 26px !important;
        letter-spacing: 0.01em !important;
        transition: all 0.25s cubic-bezier(.34,1.56,.64,1) !important;
        box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #047857 0%, #0369a1 100%) !important;
        box-shadow: 0 8px 24px rgba(5, 150, 105, 0.4) !important;
        transform: translateY(-2px) !important;
        color: #ffffff !important;
    }

    /* ─── File uploader ─── */
    [data-testid="stFileUploader"] {
        background: #1e293b !important;
        border: 2px dashed rgba(16, 185, 129, 0.3) !important;
        border-radius: 16px !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #059669 !important;
        background: rgba(16, 185, 129, 0.06) !important;
        box-shadow: 0 4px 16px rgba(16, 185, 129, 0.1) !important;
    }

    /* ─── Tab styling ─── */
    .stTabs [data-baseweb="tab-list"] {
        background: #1e293b !important;
        border-radius: 12px !important;
        padding: 5px !important;
        border: 1px solid #334155 !important;
        gap: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: #64748b !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 9px 22px !important;
        transition: all 0.2s ease !important;
        font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif !important;
        letter-spacing: -0.01em !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #e2e8f0 !important;
        background: rgba(255, 255, 255, 0.05) !important;
    }
    .stTabs [aria-selected="true"] {
        background: #0f172a !important;
        color: #34d399 !important;
        font-weight: 700 !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
    }

    /* ─── Progress bar ─── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #10b981, #0284c7, #6366f1) !important;
        box-shadow: 0 0 10px rgba(16, 185, 129, 0.35) !important;
        border-radius: 6px !important;
    }
    .stProgress > div > div > div {
        background: #334155 !important;
        border-radius: 6px !important;
    }

    /* ─── Sidebar stat chip ─── */
    .stat-chip {
        display: flex;
        align-items: center;
        gap: 9px;
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 9px 14px;
        margin-bottom: 8px;
        font-size: 0.80rem;
        color: #94a3b8;
        font-weight: 500;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        transition: all 0.2s ease;
    }
    .stat-chip:hover {
        background: rgba(16, 185, 129, 0.08);
        border-color: rgba(16, 185, 129, 0.3);
        color: #34d399;
    }
    .stat-chip .chip-val {
        color: #10b981;
        font-weight: 700;
        margin-left: auto;
        font-size: 0.86rem;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ─── Scrollbar ─── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }

    /* ─── Code blocks ─── */
    pre, code {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        color: #38bdf8 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ─── Radar pulse animation ─── */
    @keyframes radar-pulse {
        0%   { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.55); }
        60%  { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .live-dot {
        display: inline-block;
        width: 9px; height: 9px;
        background: #059669;
        border-radius: 50%;
        animation: radar-pulse 1.8s infinite;
        vertical-align: middle;
        margin-right: 6px;
        box-shadow: 0 0 6px rgba(5, 150, 105, 0.7);
    }

    /* ─── About cards ─── */
    .about-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 22px 24px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        transition: border-color 0.25s ease, box-shadow 0.25s ease;
    }
    .about-card:hover {
        border-color: rgba(16, 185, 129, 0.3);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    .about-card h3 {
        color: #34d399 !important;
        font-family: 'Outfit', sans-serif !important;
        font-size: 0.98rem;
        margin-top: 0 !important;
    }

    /* ─── Selectbox popovers & menus ─── */
    [data-baseweb="select"] [data-baseweb="popover"],
    [data-baseweb="menu"] {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4) !important;
        color: #e2e8f0 !important;
    }
    [data-baseweb="menu"] [role="option"] {
        color: #cbd5e1 !important;
    }
    [data-baseweb="menu"] [role="option"]:hover {
        background: rgba(16, 185, 129, 0.1) !important;
        color: #34d399 !important;
    }

    /* ─── Animated number counter helper ─── */
    .counter-num {
        display: inline-block;
        animation: count-in 0.6s cubic-bezier(.22,.61,.36,1) both;
    }
    @keyframes count-in {
        from { opacity: 0; transform: translateY(12px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ─── Image display frames ─── */
    .stImage img {
        border-radius: 12px !important;
        border: 1px solid #334155 !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
        transition: box-shadow 0.3s ease !important;
    }
    .stImage img:hover {
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4) !important;
    }

    /* ─── Native expanders & widgets ─── */
    [data-testid="stExpander"] {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════
# Session-state helpers
# ══════════════════════════════════════════════════════════════════

def _init_session_state() -> None:
    defaults = {
        "cfg": None,
        "model": None,
        "model_path_loaded": None,
        "class_names": ["animal"],
        "is_trained": False,
        "mode_label": "Not loaded",
        "last_image_detections": [],
        "last_video_summary": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════════
# Model loading (cached per checkpoint path)
# ══════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="Loading model…")
def _load_model(checkpoint_path: str) -> Any:
    """Load and cache a YOLO model. Re-runs only when checkpoint_path changes."""
    try:
        from ultralytics import YOLO
        return YOLO(checkpoint_path)
    except Exception as exc:
        return exc   # Return the exception object; handle downstream


def _load_config_cached() -> dict[str, Any]:
    """Load config (cached in session state)."""
    if st.session_state.cfg is None:
        try:
            st.session_state.cfg = load_config()
        except FileNotFoundError as exc:
            st.error(f"Configuration file not found:\n\n{exc}")
            st.stop()
    return st.session_state.cfg


# ══════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════

def _render_sidebar(cfg: dict[str, Any]) -> tuple[str, float, float, int, int]:
    """Render the sidebar controls and return chosen settings."""
    st.sidebar.markdown(
        """
        <div style='
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.9));
            border: 1px solid rgba(16, 185, 129, 0.25);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 16px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        '>
          <div style='position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,transparent,#10b981,#0284c7,transparent);'></div>
          <div style='font-family:"Outfit",sans-serif;font-size:1.08rem;
            font-weight:800;background:linear-gradient(90deg,#34d399,#38bdf8);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            background-clip:text;letter-spacing:-0.01em;'>🌿 Wildlife Radar</div>
          <div style='color:#94a3b8;font-size:0.72rem;margin-top:3px;
            font-family:"JetBrains Mono",monospace;letter-spacing:0.06em;font-weight:600;'>
            WESTERN GHATS · TN &amp; KL</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Model checkpoint selector ────────────────────────────────
    st.sidebar.markdown("### 🧠 Model Checkpoint")
    available_checkpoints: list[str] = []

    # 1. User-trained model
    trained_ckpt = cfg.get("model", {}).get("trained_checkpoint")
    if trained_ckpt and Path(trained_ckpt).is_file():
        available_checkpoints.append(trained_ckpt)

    # 2. Scan runs/ for additional .pt files
    runs_dir = Path(cfg["paths"]["runs_dir"])
    if runs_dir.exists():
        for pt in sorted(runs_dir.rglob("best.pt")):
            if str(pt) not in available_checkpoints:
                available_checkpoints.append(str(pt))
        for pt in sorted(runs_dir.rglob("last.pt")):
            if str(pt) not in available_checkpoints:
                available_checkpoints.append(str(pt))

    # 3. Generic pretrained
    pretrained = cfg.get("model", {}).get("pretrained_checkpoint", "yolov8n.pt")
    if pretrained not in available_checkpoints:
        available_checkpoints.append(pretrained)

    selected_ckpt = st.sidebar.selectbox(
        "Checkpoint",
        options=available_checkpoints,
        format_func=lambda p: Path(p).name,
        key="ckpt_selector",
    )

    # ── Inference parameters ─────────────────────────────────────
    st.sidebar.markdown("### ⚙️ Inference Settings")
    conf_thresh = st.sidebar.slider(
        "Confidence Threshold",
        min_value=0.05,
        max_value=0.95,
        value=float(cfg.get("model", {}).get("confidence_threshold", 0.25)),
        step=0.05,
        help="Detections below this confidence are discarded.",
    )
    iou_thresh = st.sidebar.slider(
        "IoU Threshold (NMS)",
        min_value=0.10,
        max_value=0.90,
        value=float(cfg.get("model", {}).get("iou_threshold", 0.45)),
        step=0.05,
        help="Threshold for Non-Maximum Suppression.",
    )
    max_det = st.sidebar.number_input(
        "Max Detections",
        min_value=1,
        max_value=1000,
        value=int(cfg.get("model", {}).get("max_det", 300)),
        step=10,
    )
    frame_skip = st.sidebar.number_input(
        "Video Frame Skip",
        min_value=1,
        max_value=30,
        value=int(cfg.get("app", {}).get("video_frame_skip", 1)),
        step=1,
        help="Process every Nth frame (1 = all frames). Higher values = faster but less complete.",
    )

    st.sidebar.markdown(
        "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:14px 0'>",
        unsafe_allow_html=True,
    )

    # ── Project Report Download ───────────────────────────────────────────
    report_file = PROJECT_ROOT / "Western_Ghats_Wildlife_Detection_Project_Report.docx"
    if report_file.exists():
        st.sidebar.markdown(
            "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:14px 0'>",
            unsafe_allow_html=True,
        )
        st.sidebar.markdown("### 📄 Academic Report")
        with open(report_file, "rb") as f:
            st.sidebar.download_button(
                label="📥 Download Project Report (.docx)",
                data=f,
                file_name="Western_Ghats_Wildlife_Detection_Project_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                help="Download full editable academic project report formatted for Anna University / Sona College of Technology",
            )


    st.sidebar.markdown(
        """
        <hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:16px 0'>
        <div style='font-size:0.70rem;color:#64748b;font-family:"JetBrains Mono",monospace;
          letter-spacing:0.04em;line-height:1.7;font-weight:500;'>
          ⚡ Ultralytics YOLO &nbsp;·&nbsp; OpenCV<br>
          <span style='color:#94a3b8;'>AI-Powered Wildlife Detection</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return selected_ckpt, conf_thresh, iou_thresh, int(max_det), int(frame_skip)



# ══════════════════════════════════════════════════════════════════
# Mode banner
# ══════════════════════════════════════════════════════════════════

def _render_mode_banner(mode: str, class_names: list[str]) -> None:
    if mode == "trained":
        badge = '<span class="badge badge-trained">✅ Trained Model</span>'
        msg   = (
            f"Custom-trained model active. Recognises: "
            f"<b>{', '.join(class_names)}</b>. "
            "Results are specific to your Western Ghats training dataset."
        )
        cls   = "trained"
    elif mode == "generic":
        badge = '<span class="badge badge-generic">⚠️ Generic Pretrained Model</span>'
        msg   = (
            "Using a <b>generic COCO-pretrained model</b>. "
            "It can detect common animals but <b>cannot identify endangered species by name</b> "
            "unless you train it on your own labelled data."
        )
        cls   = "generic"
    else:
        badge = '<span class="badge badge-nomodel">❌ No Model Loaded</span>'
        msg   = "No model is currently loaded. Check the sidebar and ensure Ultralytics is installed."
        cls   = "nomodel"

    st.markdown(
        f'<div class="mode-banner {cls}">'
        f'  <div style="flex-shrink:0;">{badge}</div>'
        f'  <div style="font-size:0.86rem;">{msg}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )



# ══════════════════════════════════════════════════════════════════
# Detection results display
# ══════════════════════════════════════════════════════════════════

def _render_detection_table(detections: list[dict[str, Any]]) -> None:
    """Render a styled HTML table of detections with percentage confidence."""
    if not detections:
        st.markdown(
            '<div class="info-box">ℹ️ No animals detected in this image at the current '
            "confidence threshold. Try lowering the threshold in the sidebar.</div>",
            unsafe_allow_html=True,
        )
        return

    rows = ""
    for i, d in enumerate(detections, start=1):
        conf = d["confidence"]
        pct = conf * 100.0
        bar_w = int(pct)
        display_name = d["class_name"].replace("_", " ").title()
        rows += (
            f"<tr>"
            f"<td>{i}</td>"
            f"<td><b>{display_name}</b> <span style='font-size:0.75rem;color:#64748b;'>({d['class_name']})</span></td>"
            f"<td>"
            f"  <div class='conf-bar-bg'><div class='conf-bar-fill' style='width:{bar_w}%'></div></div>"
            f"  <span style='font-size:0.86rem;font-weight:700;color:#0284c7;'>{pct:.1f}%</span> "
            f"  <span style='font-size:0.75rem;color:#64748b;'>({conf:.3f})</span>"
            f"</td>"
            f"<td style='font-size:0.8rem;color:#64748b;font-family:\"JetBrains Mono\",monospace;'>"
            f"  [{d['bbox_xyxy'][0]:.0f}, {d['bbox_xyxy'][1]:.0f}, "
            f"   {d['bbox_xyxy'][2]:.0f}, {d['bbox_xyxy'][3]:.0f}]"
            f"</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <table class='det-table'>
          <thead><tr>
            <th>#</th><th>Species</th><th>Confidence (%)</th><th>BBox [x1, y1, x2, y2]</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def _render_species_cards(
    detections: list[dict[str, Any]],
    species_info: dict[str, dict[str, str]],
) -> None:
    """Render structured IUCN species cards for detected animals."""
    if not detections or not species_info:
        return

    # Find unique detected classes that have species_info
    detected_classes = list(dict.fromkeys(d["class_name"] for d in detections))
    relevant_species = [cls for cls in detected_classes if cls in species_info]

    if not relevant_species:
        return

    st.markdown("<div class='section-header'>🌿 Western Ghats Species & IUCN Conservation Info</div>", unsafe_allow_html=True)

    iucn_colors = {
        "CR": {"border": "#ef4444", "bg": "rgba(239, 68, 68, 0.12)", "badge_bg": "rgba(239, 68, 68, 0.25)", "text": "#fca5a5"},
        "EN": {"border": "#f97316", "bg": "rgba(249, 115, 22, 0.12)", "badge_bg": "rgba(249, 115, 22, 0.25)", "text": "#fdba74"},
        "VU": {"border": "#eab308", "bg": "rgba(234, 179, 8, 0.12)", "badge_bg": "rgba(234, 179, 8, 0.25)", "text": "#fde047"},
        "NT": {"border": "#10b981", "bg": "rgba(16, 185, 129, 0.12)", "badge_bg": "rgba(16, 185, 129, 0.25)", "text": "#86efac"},
        "LC": {"border": "#059669", "bg": "rgba(5, 150, 105, 0.12)", "badge_bg": "rgba(5, 150, 105, 0.25)", "text": "#6ee7b7"},
    }

    cols = st.columns(2) if len(relevant_species) > 1 else [st.container()]
    for idx, sp_key in enumerate(relevant_species):
        info = species_info[sp_key]
        sp_detections = [d for d in detections if d["class_name"] == sp_key]
        max_conf = max(d["confidence"] for d in sp_detections)
        count = len(sp_detections)
        iucn_code = info.get("iucn_code", "VU")
        style = iucn_colors.get(iucn_code, iucn_colors["VU"])

        display_name = sp_key.replace("_", " ").title()
        sci_name = info.get("scientific_name", "")
        status = info.get("iucn_status", "")
        region = info.get("region", "")
        desc = info.get("description", "")

        card_html = (
            f"<div class='species-card' style='background:{style['bg']}; border-left: 5px solid {style['border']};'>"
            f"  <div style='display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 8px;'>"
            f"    <div>"
            f"      <span style='font-size:1.15rem; font-weight:700; color:#f1f5f9;'>{display_name}</span>"
            f"      <div style='font-style:italic; font-size:0.84rem; color:#94a3b8;'>{sci_name}</div>"
            f"    </div>"
            f"    <div style='text-align:right;'>"
            f"      <span style='background:{style['badge_bg']}; color:{style['text']}; font-weight:700; "
            f"      font-size:0.75rem; padding:3px 9px; border-radius:12px; border:1px solid {style['border']};'>"
            f"        IUCN: {iucn_code} — {status}"
            f"      </span>"
            f"      <div style='font-size:0.83rem; color:#38bdf8; font-weight:700; margin-top:4px;'>"
            f"        {max_conf * 100:.1f}% confidence ({count} detected)"
            f"      </div>"
            f"    </div>"
            f"  </div>"
            f"  <div style='font-size:0.83rem; color:#cbd5e1; margin-bottom:6px;'>"
            f"    <b style='color:#38bdf8;'>📍 Western Ghats Range:</b> {region}"
            f"  </div>"
            f"  <div style='font-size:0.82rem; color:#94a3b8; line-height:1.45;'>"
            f"    <b style='color:#38bdf8;'>ℹ️ Conservation Profile:</b> {desc}"
            f"  </div>"
            f"</div>"
        )
        if len(relevant_species) > 1:
            with cols[idx % 2]:
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.markdown(card_html, unsafe_allow_html=True)


def _metrics_row(n_det: int, n_classes: int, elapsed_ms: float) -> None:
    """Render holographic metric cards in a 3-column row."""
    col1, col2, col3 = st.columns(3)
    metrics = [
        (col1, "🎯", str(n_det),           "Detections"),
        (col2, "🦎", str(n_classes),        "Unique Species"),
        (col3, "⚡", f"{elapsed_ms:.0f}ms", "Inference Time"),
    ]
    for col, icon, val, label in metrics:
        with col:
            st.markdown(
                f"<div class='metric-card'>"
                f"  <span class='metric-icon'>{icon}</span>"
                f"  <span class='metric-value counter-num'>{val}</span>"
                f"  <div class='metric-sep'></div>"
                f"  <div class='metric-label'>{label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )



# ══════════════════════════════════════════════════════════════════
# Download helpers
# ══════════════════════════════════════════════════════════════════

def _detections_to_csv(detections: list[dict[str, Any]]) -> str:
    """Convert detection list to CSV string."""
    if not detections:
        return "class_id,class_name,confidence,x1,y1,x2,y2\n"
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["class_id", "class_name", "confidence", "x1", "y1", "x2", "y2"],
    )
    writer.writeheader()
    for d in detections:
        b = d["bbox_xyxy"]
        writer.writerow(
            {
                "class_id": d["class_id"],
                "class_name": d["class_name"],
                "confidence": d["confidence"],
                "x1": b[0],
                "y1": b[1],
                "x2": b[2],
                "y2": b[3],
            }
        )
    return buf.getvalue()


def _image_to_bytes(bgr_image: np.ndarray, ext: str = ".jpg") -> bytes:
    """Encode a BGR numpy image to bytes."""
    success, buf = cv2.imencode(ext, bgr_image)
    if not success:
        raise ValueError("Failed to encode image.")
    return buf.tobytes()


# ══════════════════════════════════════════════════════════════════
# Shared inference + display helper (used by both upload & camera)
# ══════════════════════════════════════════════════════════════════

def _run_and_display(
    bgr: np.ndarray,
    filename: str,
    model: Any,
    class_names: list[str],
    is_trained: bool,
    conf_thresh: float,
    iou_thresh: float,
    max_det: int,
    cfg: dict[str, Any],
) -> None:
    """Run inference on a BGR image and render all results + download buttons."""
    t0 = time.perf_counter()
    annotated, detections = run_inference(
        model=model,
        image=bgr,
        class_names=class_names,
        conf_threshold=conf_thresh,
        iou_threshold=iou_thresh,
        max_det=max_det,
        is_trained=is_trained,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    mode_str = "Trained" if is_trained else "Generic"
    annotated_overlay = draw_status_overlay(annotated, mode_str, len(detections))

    # Side-by-side: original | annotated
    col_orig, col_ann = st.columns(2)
    with col_orig:
        st.markdown("**Original**")
        st.image(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), use_container_width=True)
    with col_ann:
        st.markdown("**Detected**")
        st.image(cv2.cvtColor(annotated_overlay, cv2.COLOR_BGR2RGB), use_container_width=True)

    # Metrics row
    n_classes = len({d["class_name"] for d in detections})
    _metrics_row(len(detections), n_classes, elapsed_ms)

    # Detection table
    st.markdown("<div class='section-header'>🔍 Detection Results</div>", unsafe_allow_html=True)
    _render_detection_table(detections)

    # IUCN species cards
    _render_species_cards(detections, get_species_info(cfg))

    # Downloads
    st.markdown("<div class='section-header'>💾 Download Results</div>", unsafe_allow_html=True)
    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "⬇️ Annotated Image",
            data=_image_to_bytes(annotated, ".jpg"),
            file_name=f"detected_{filename}",
            mime="image/jpeg",
        )
    with dl2:
        st.download_button(
            "⬇️ CSV Results",
            data=_detections_to_csv(detections),
            file_name=f"detections_{filename}.csv",
            mime="text/csv",
        )
    with dl3:
        st.download_button(
            "⬇️ JSON Results",
            data=json.dumps(detections, indent=2),
            file_name=f"detections_{filename}.json",
            mime="application/json",
        )

    st.session_state.last_image_detections = detections


# ══════════════════════════════════════════════════════════════════
# Photo tab  (Upload  +  Live Camera sub-tabs)
# ══════════════════════════════════════════════════════════════════

def _tab_photo(
    model: Any,
    class_names: list[str],
    is_trained: bool,
    conf_thresh: float,
    iou_thresh: float,
    max_det: int,
    cfg: dict[str, Any],
) -> None:
    supported = cfg.get("app", {}).get("supported_image_formats", ["jpg", "jpeg", "png"])

    st.markdown("<div class='section-header'>📷 Photo Detection</div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;'>"
        "Choose <b>Upload Image</b> to analyse a saved photo, or use "
        "<b>📸 Live Camera</b> to snap a photo directly from your webcam.</p>",
        unsafe_allow_html=True,
    )

    sub_upload, sub_camera = st.tabs(["🖼️ Upload Image", "📸 Live Camera"])

    # ── Sub-tab: File Upload ──────────────────────────────────────
    with sub_upload:
        uploaded = st.file_uploader(
            "Choose an image file",
            type=supported,
            key="photo_uploader",
        )
        if uploaded is None:
            st.markdown(
                "<div class='info-box'>ℹ️ Upload a JPG, PNG, or BMP image to run detection.</div>",
                unsafe_allow_html=True,
            )
            return

        file_bytes = np.frombuffer(uploaded.read(), dtype=np.uint8)
        bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if bgr is None:
            st.markdown(
                "<div class='error-box'>❌ Could not decode the uploaded image. "
                "Please try a different file.</div>",
                unsafe_allow_html=True,
            )
            return

        _run_and_display(
            bgr=bgr,
            filename=uploaded.name,
            model=model,
            class_names=class_names,
            is_trained=is_trained,
            conf_thresh=conf_thresh,
            iou_thresh=iou_thresh,
            max_det=max_det,
            cfg=cfg,
        )

    # ── Sub-tab: Live Camera ──────────────────────────────────────
    with sub_camera:
        st.markdown(
            "<p style='color:#94a3b8;font-size:0.85rem;'>"
            "🔒 Your browser will ask for camera permission the first time. "
            "Click <b>Take Photo</b> to capture a frame, then detection runs automatically.</p>",
            unsafe_allow_html=True,
        )

        camera_img = st.camera_input(
            label="Point camera at an animal and press Take Photo",
            key="camera_capture",
        )

        if camera_img is None:
            st.markdown(
                "<div class='info-box'>ℹ️ Grant camera access above, then click "
                "<b>Take Photo</b> to run detection on the captured frame.</div>",
                unsafe_allow_html=True,
            )
            return

        file_bytes = np.frombuffer(camera_img.read(), dtype=np.uint8)
        bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if bgr is None:
            st.markdown(
                "<div class='error-box'>❌ Could not read the camera frame. "
                "Please try again.</div>",
                unsafe_allow_html=True,
            )
            return

        _run_and_display(
            bgr=bgr,
            filename="camera_capture.jpg",
            model=model,
            class_names=class_names,
            is_trained=is_trained,
            conf_thresh=conf_thresh,
            iou_thresh=iou_thresh,
            max_det=max_det,
            cfg=cfg,
        )


# ══════════════════════════════════════════════════════════════════
# Video tab
# ══════════════════════════════════════════════════════════════════

def _tab_video(
    model: Any,
    class_names: list[str],
    is_trained: bool,
    conf_thresh: float,
    iou_thresh: float,
    max_det: int,
    frame_skip: int,
    cfg: dict[str, Any],
) -> None:
    from src.video_processor import process_video

    supported = cfg.get("app", {}).get("supported_video_formats", ["mp4", "avi", "mov"])

    st.markdown("<div class='section-header'>🎬 Upload a Video</div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94a3b8;font-size:0.85rem;'>"
        "Video is processed <b>frame-by-frame</b> using OpenCV — the entire file is "
        "never loaded into memory. Large videos may take several minutes on CPU.</p>"
        "<p style='color:#94a3b8;font-size:0.85rem;'>"
        "⚠️ Live webcam input is not supported in this environment. Use a pre-recorded video file.</p>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Choose a video file",
        type=supported,
        key="video_uploader",
    )
    if uploaded is None:
        return

    max_mb = cfg.get("app", {}).get("max_upload_size_mb", 200)
    size_mb = len(uploaded.getvalue()) / 1_048_576
    if size_mb > max_mb:
        st.markdown(
            f"<div class='error-box'>❌ File too large ({size_mb:.1f} MB). "
            f"Maximum allowed: {max_mb} MB.</div>",
            unsafe_allow_html=True,
        )
        return

    if st.button("▶ Process Video", key="process_video_btn"):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save uploaded file to temp location
            input_path = Path(tmpdir) / uploaded.name
            input_path.write_bytes(uploaded.getvalue())
            output_path = Path(tmpdir) / f"detected_{uploaded.name}"

            progress_bar = st.progress(0, text="Processing video…")

            def _progress_cb(frame_idx: int, total: int) -> None:
                pct = int(100 * frame_idx / max(total, 1))
                progress_bar.progress(min(pct, 100), text=f"Frame {frame_idx}/{total}")

            t0 = time.perf_counter()
            try:
                summary = process_video(
                    video_path=input_path,
                    output_path=output_path,
                    model=model,
                    class_names=class_names,
                    conf_threshold=conf_thresh,
                    iou_threshold=iou_thresh,
                    max_det=max_det,
                    frame_skip=frame_skip,
                    is_trained=is_trained,
                    progress_callback=_progress_cb,
                )
            except Exception as exc:
                st.markdown(
                    f"<div class='error-box'>❌ Video processing failed: {exc}</div>",
                    unsafe_allow_html=True,
                )
                return

            elapsed_total = time.perf_counter() - t0
            progress_bar.progress(100, text="Done!")

            # Metrics
            n_det = summary["total_detections"]
            n_proc = summary["processed_frames"]
            fps = summary["average_fps"]

            col1, col2, col3, col4 = st.columns(4)
            for col, val, lbl in [
                (col1, n_det, "Total Detections"),
                (col2, n_proc, "Frames Processed"),
                (col3, f"{fps:.1f}", "Avg FPS"),
                (col4, f"{elapsed_total:.1f}s", "Total Time"),
            ]:
                col.markdown(
                    f"<div class='metric-card'>"
                    f"  <div class='metric-value'>{val}</div>"
                    f"  <div class='metric-label'>{lbl}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            if not output_path.exists():
                st.markdown(
                    "<div class='error-box'>❌ Output video was not created. Check logs.</div>",
                    unsafe_allow_html=True,
                )
                return

            # Download buttons
            st.markdown("<div class='section-header'>💾 Download Results</div>", unsafe_allow_html=True)
            vid_bytes = output_path.read_bytes()
            det_list = summary.get("detections", [])

            # IUCN Species Information Cards
            if det_list:
                _render_species_cards(det_list, get_species_info(cfg))

            dl1, dl2, dl3 = st.columns(3)
            with dl1:
                st.download_button(
                    "⬇️ Annotated Video",
                    data=vid_bytes,
                    file_name=f"detected_{uploaded.name}",
                    mime="video/mp4",
                )
            with dl2:
                st.download_button(
                    "⬇️ CSV Results",
                    data=_detections_to_csv(det_list),
                    file_name=f"detections_{uploaded.name}.csv",
                    mime="text/csv",
                )
            with dl3:
                st.download_button(
                    "⬇️ JSON Summary",
                    data=json.dumps(summary, indent=2),
                    file_name=f"summary_{uploaded.name}.json",
                    mime="application/json",
                )

            st.session_state.last_video_summary = summary

            st.markdown(
                f"<div class='success-box'>✅ Video processed successfully. "
                f"{n_det} detection(s) across {n_proc} frame(s).</div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════
# Setup guide (shown when no model is loaded)
# ══════════════════════════════════════════════════════════════════

def _render_setup_guide() -> None:
    st.markdown(
        """
        <div class='warning-box'>
        <b>⚠️ Setup Required</b><br><br>
        The YOLO model failed to load. This is usually because <code>ultralytics</code>
        is not installed, or the checkpoint file is missing.<br><br>
        <b>Quick setup steps (Windows):</b><br>
        <pre style='background:#1a1a2e;padding:10px;border-radius:6px;color:#90cdf4;font-size:0.85rem;'>
# 1. Create and activate a virtual environment
python -m venv venv
venv\\Scripts\\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app/app.py</pre>
        The app will use a generic pretrained YOLO model until you train your own.<br>
        See <b>README.md</b> for the full setup guide.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════
# Main app
# ══════════════════════════════════════════════════════════════════

def main() -> None:
    _init_session_state()
    cfg = _load_config_cached()

    # ── Sidebar ──────────────────────────────────────────────────
    selected_ckpt, conf_thresh, iou_thresh, max_det, frame_skip = _render_sidebar(cfg)

    # ── Load model (cached by checkpoint path) ───────────────────
    model_or_error = _load_model(selected_ckpt)
    model_ok = not isinstance(model_or_error, Exception)

    if model_ok:
        model = model_or_error
        # Determine mode
        is_trained = is_trained_model_available(cfg) and selected_ckpt == cfg.get("model", {}).get(
            "trained_checkpoint"
        )
        mode = "trained" if is_trained else "generic"

        # Resolve class names
        if is_trained:
            class_names = get_class_names(cfg)
        else:
            # Generic COCO model: use YOLO's built-in names
            try:
                class_names = list(model.names.values())
            except Exception:
                class_names = get_class_names(cfg)
    else:
        model = None
        is_trained = False
        mode = "nomodel"
        class_names = get_class_names(cfg)

    # ── Hero Header ──────────────────────────────────────────────
    st.markdown(
        """
        <div class='hero-banner'>
          <div class='scan-line'></div>
          <div class='hero-orb1'></div>
          <div class='hero-orb2'></div>
          <div class='hero-title'>🌿 Western Ghats Wildlife Radar</div>
          <p class='hero-sub'>AI-POWERED ENDANGERED ANIMAL DETECTION &nbsp;|&nbsp; TAMIL NADU &amp; KERALA</p>
          <div class='hero-tags'>
            <span class='hero-tag'>YOLOv8</span>
            <span class='hero-tag'>Real-Time</span>
            <span class='hero-tag'>IUCN Species</span>
            <span class='hero-tag'>Western Ghats</span>
            <span class='hero-tag'>Computer Vision</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_mode_banner(mode, class_names)

    if not model_ok:
        _render_setup_guide()
        st.markdown(
            f"<div class='error-box'>Model load error: <code>{model_or_error}</code></div>",
            unsafe_allow_html=True,
        )
        return

    # ── Tabs ─────────────────────────────────────────────────────
    tab_photo, tab_video, tab_about = st.tabs(["📷 Photo", "🎬 Video", "ℹ️ About"])

    with tab_photo:
        _tab_photo(
            model=model,
            class_names=class_names,
            is_trained=is_trained,
            conf_thresh=conf_thresh,
            iou_thresh=iou_thresh,
            max_det=max_det,
            cfg=cfg,
        )

    with tab_video:
        _tab_video(
            model=model,
            class_names=class_names,
            is_trained=is_trained,
            conf_thresh=conf_thresh,
            iou_thresh=iou_thresh,
            max_det=max_det,
            frame_skip=frame_skip,
            cfg=cfg,
        )

    with tab_about:
        _render_about(cfg, class_names, is_trained, selected_ckpt)


# ══════════════════════════════════════════════════════════════════
# About tab
# ══════════════════════════════════════════════════════════════════

def _render_about(
    cfg: dict[str, Any],
    class_names: list[str],
    is_trained: bool,
    checkpoint: str,
) -> None:
    species_info = get_species_info(cfg)
    project_meta = get_project_metadata(cfg)

    st.markdown(
        """
        ## 🌿 Western Ghats Endangered Animal Detection
        **Tamil Nadu & Kerala Biodiversity Monitoring Prototype**

        This system is an AI-powered detection tool specifically calibrated for **endangered and vulnerable wildlife**
        inhabiting the **Western Ghats biodiversity hotspot**, with an emphasis on protected reserves in **Tamil Nadu and Kerala**
        (e.g., Nilgiri Biosphere, Anamalai Tiger Reserve, Mudumalai, Wayanad, and Periyar).

        ---
        ### 📋 Focused Species Catalog
        The detector is configured for 10 high-priority indicator and threatened species:
        """,
    )

    # Render catalog table
    catalog_rows = ""
    for idx, cname in enumerate(class_names):
        info = species_info.get(cname, {})
        sci = info.get("scientific_name", "—")
        status = info.get("iucn_status", "—")
        code = info.get("iucn_code", "")
        region = info.get("region", "—")
        dname = cname.replace("_", " ").title()

        badge_color = "#e53e3e" if code == "CR" else "#dd6b20" if code == "EN" else "#d69e2e"
        status_html = (
            f"<span style='background:{badge_color}22; color:{badge_color}; border:1px solid {badge_color}; "
            f"padding:2px 8px; border-radius:10px; font-weight:700; font-size:0.75rem;'>"
            f"[{code}] {status}</span>"
        )
        catalog_rows += (
            f"<tr>"
            f"<td style='text-align:center;color:#0284c7;font-weight:600;font-family:\"JetBrains Mono\",monospace;'>{idx}</td>"
            f"<td><b>{dname}</b></td>"
            f"<td><i>{sci}</i></td>"
            f"<td>{status_html}</td>"
            f"<td style='font-size:0.82rem;color:#94a3b8;'>{region}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <table class='det-table' style='margin-bottom:20px;'>
          <thead><tr>
            <th style='width:5%;'>ID</th>
            <th style='width:25%;'>Common Name</th>
            <th style='width:25%;'>Scientific Name</th>
            <th style='width:20%;'>IUCN Red List Status</th>
            <th style='width:25%;'>Western Ghats Occurrence</th>
          </tr></thead>
          <tbody>{catalog_rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        ---
        ### 🎯 Small-Dataset Optimization & Scalability

        Wildlife imagery for rare species like the *Malabar Civet* or *Nilgiri Marten* is notoriously scarce.
        This system is engineered to deliver reliable feature learning even with **5 to 20 images per species**:

        1. **Transfer Learning**: Built upon the YOLOv8s architecture, preserving foundational vision representations (edges, textures, silhouettes) while fine-tuning higher-level animal features.
        2. **Domain-Specific Augmentation**: Aggressive HSV color jitter (simulating varied forest lighting), random scaling (0.6), rotation (15°), horizontal flips, and MixUp (0.1) synthesize diverse realistic sightings.
        3. **Mosaic & Close-Mosaic Scheduling**: Quad-image mosaic augmentation exposes the model to varied animal scales, automatically disabling in the final 20 epochs (`close_mosaic: 20`) to stabilize bounding box precision.
        4. **Incremental Dataset Growth**: As new field photos, camera-trap sightings, or PDF extracts become available, you can seamlessly ingest them using the included pipeline tool.

        ---
        ### 📥 Adding New Images in the Future
        To ingest and index new images without manual folder management, use `scripts/add_images.py`:
        """,
    )

    col_add1, col_add2 = st.columns(2)
    with col_add1:
        st.markdown("**1. Adding Labelled Pairs (Image + YOLO .txt):**")
        st.code(
            "# Automatically validates pairs, avoids duplicates, and routes to train/val\n"
            "python scripts/add_images.py \\\n"
            "  --source path/to/folder \\\n"
            "  --species nilgiri_tahr \\\n"
            "  --mode labelled \\\n"
            "  --split train",
            language="bash",
        )
    with col_add2:
        st.markdown("**2. Adding Raw Unannotated Images:**")
        st.code(
            "# Stages images into data/raw/ ready for annotation in LabelImg\n"
            "python scripts/add_images.py \\\n"
            "  --source path/to/folder \\\n"
            "  --species lion_tailed_macaque \\\n"
            "  --mode raw",
            language="bash",
        )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ⚙️ Active System Configuration")
        st.json(
            {
                "project": project_meta.get("name", "Western Ghats Animal Detector"),
                "region": project_meta.get("region", "Tamil Nadu & Kerala"),
                "checkpoint": Path(checkpoint).name,
                "mode": "trained" if is_trained else "generic_pretrained",
                "active_classes": len(class_names),
                "confidence_threshold": cfg.get("model", {}).get("confidence_threshold"),
                "iou_threshold": cfg.get("model", {}).get("iou_threshold"),
            }
        )
    with col2:
        st.markdown("### 🚀 Workflow Commands")
        st.code(
            "# 1. Ingest new images\n"
            "python scripts/add_images.py --source <dir> --species <name>\n\n"
            "# 2. Validate dataset integrity\n"
            "python scripts/validate_dataset.py\n\n"
            "# 3. Train detector (optimized for small datasets)\n"
            "python scripts/train.py\n\n"
            "# 4. Evaluate performance\n"
            "python scripts/evaluate.py\n\n"
            "# 5. Launch web application\n"
            "streamlit run app/app.py",
            language="bash",
        )

    st.markdown(
        """
        ---
        ### ⚠️ Academic Prototype & Conservation Notice
        - **Prototype Disclaimer**: This application is an educational prototype and should not be used as an automated sole decision-maker for anti-poaching or field wildlife enforcement without human verification.
        - **Species Identification**: The model's classification relies strictly on visible morphological characteristics in the trained dataset. High occlusions, dense canopy, or nocturnal IR lighting may affect confidence scores.

        ### 📚 References & Resources
        - [IUCN Red List of Threatened Species](https://www.iucnredlist.org/)
        - [Wildlife Institute of India (WII)](https://www.wii.gov.in/)
        - [Kerala Forest and Wildlife Department](https://forest.kerala.gov.in/)
        - [Tamil Nadu Forest Department](https://www.forests.tn.gov.in/)
        - [Ultralytics YOLOv8 Documentation](https://docs.ultralytics.com/)
        """,
    )


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
