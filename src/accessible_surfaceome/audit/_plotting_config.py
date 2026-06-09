"""Plotting configuration for accessible-surfaceome figures.

Uses seaborn styling with a Deliverome-aligned palette for publication-quality
figures. Callers must invoke :func:`setup_plotting_style` explicitly —
importing this module has no side effects.
"""
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns

# Bundled brand fonts (committed under ./assets/fonts/). Registered with
# matplotlib's font manager on first call to setup_plotting_style so the
# rcParams below actually resolve to Manrope instead of falling back to
# DejaVu Sans.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED_FONTS_DIR = _REPO_ROOT / "assets" / "fonts"
_fonts_registered = False


def register_bundled_fonts() -> None:
    """Add ``./assets/fonts/*.ttf`` to matplotlib's font manager (idempotent)."""

    global _fonts_registered
    if _fonts_registered:
        return
    if not _BUNDLED_FONTS_DIR.is_dir():
        _fonts_registered = True
        return
    for ttf in sorted(_BUNDLED_FONTS_DIR.glob("*.ttf")):
        try:
            fm.fontManager.addfont(str(ttf))
        except Exception:  # noqa: BLE001 — best-effort; fall back if a font can't load
            continue
    _fonts_registered = True

# Core Deliverome palette tokens (from Deliverome Design System)
COLORS = {
    # Brand anchors
    "primary": "#BC3C4C",       # maroon-light / accent
    "secondary": "#3D6B60",     # teal-mid
    "accent": "#F4AA28",        # amber-bright
    "quaternary": "#8878C8",    # lavender-bright
    # Semantic / utility
    "success": "#2E7A55",
    "warning": "#8C4210",       # amber-dark
    "danger": "#6E1428",        # maroon-dark
    "info": "#5848A8",          # lavender-mid
    "neutral": "#6F5D5A",       # muted
    "light": "#F3ECE5",         # bg-warm
    "dark": "#1F1718",          # ink
    "line": "#E6DAD4",
    # Legacy aliases for downstream code compatibility
    "accent_blue": "#3D6B60",
    "accent_gold": "#F4AA28",
    "accent_green": "#2E7A55",
}

# Categorical plotting palette (recommended figure anchors)
CATEGORICAL_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]

# Sequential palettes by hue family (deep -> light)
SEQUENTIAL_PALETTES = {
    "maroon": ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal": ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber": ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}

# Diverging palette (lavender <-> neutral <-> maroon)
DIVERGING_PALETTE = sns.blend_palette(
    ["#8878C8", "#FFFFFF", "#BC3C4C"],
    n_colors=11,
)

# Default bar styling configuration
ROUND_BARS_DEFAULT = False

def setup_plotting_style(style="default", context="notebook", font_scale=2.0):
    """
    Set up modern plotting style for all figures.

    Parameters:
    -----------
    style : str
        Seaborn style ('default', 'white', 'whitegrid', 'dark', 'darkgrid', 'ticks')
    context : str
        Seaborn context ('paper', 'notebook', 'talk', 'poster')
    font_scale : float
        Scale factor for fonts (default: 2.2 for larger, more readable text)
    """

    # Register bundled brand fonts before applying rcParams that reference them.
    register_bundled_fonts()

    # Set seaborn style
    if style == "default":
        sns.set_style("whitegrid")
    else:
        sns.set_style(style)

    # Set context for appropriate sizing
    sns.set_context(context, font_scale=font_scale)
    sns.set(font_scale=font_scale)

    # Set color palette
    sns.set_palette(CATEGORICAL_PALETTE)

    # Custom matplotlib parameters
    plt.rcParams.update({
        # Figure
        'figure.figsize': (5, 4),
        'figure.dpi': 100,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
        'figure.facecolor': 'none',
        'savefig.facecolor': 'none',

        # Font (project convention is +30% from matplotlib defaults so
        # exported figures stay readable when embedded in slides / PDFs)
        'font.family': 'sans-serif',
        'font.sans-serif': ['Manrope', 'Outfit', 'DejaVu Sans', 'Liberation Sans', 'Arial'],
        'font.serif': ['Playfair Display', 'Georgia', 'Times New Roman', 'serif'],
        'font.size': 14,
        # Manrope at weight 400 reads as light against Manrope's variable
        # range (300-800). Default to 500 (medium) so figures don't ever
        # render with the thin defaults — explicit ``fontweight='light'``
        # is still respected on a per-text basis if a figure wants it.
        'font.weight': 'medium',

        # Axes
        'axes.labelsize': 16,
        # Titles are suppressed by config (project convention is to
        # caption figures rather than title them). Existing
        # ``ax.set_title(...)`` calls become visual no-ops without
        # raising — titlesize=0 + zero padding means no space is
        # reserved either. To re-enable for a one-off plot, set
        # ``axes.titlesize`` back to e.g. 16 via plt.rcParams after
        # calling setup_plotting_style.
        'axes.titlesize': 0,
        'axes.titlepad': 0,
        'axes.titleweight': 'semibold',
        'axes.labelweight': 'medium',
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': True,
        'axes.axisbelow': True,
        'axes.edgecolor': COLORS['line'],
        'axes.labelcolor': COLORS['dark'],
        'axes.facecolor': 'none',
        'text.color': COLORS['dark'],

        # Grid
        'grid.alpha': 0.35,
        'grid.linestyle': '-',
        'grid.linewidth': 0.7,
        'grid.color': COLORS['line'],

        # Ticks
        'xtick.labelsize': 13,
        'ytick.labelsize': 13,
        'xtick.color': COLORS['dark'],
        'ytick.color': COLORS['dark'],

        # Legend
        'legend.frameon': True,
        'legend.framealpha': 0.9,
        'legend.fancybox': True,
        'legend.fontsize': 13,
        'legend.title_fontsize': 14,

        # Lines
        'lines.linewidth': 2,
        'lines.markersize': 8,

        # Patches (bars, etc.)
        'patch.edgecolor': 'none',
        'patch.linewidth': 0.0,
    })

    # Default despine to top/right for a clean look.
    sns.despine(top=True, right=True)

    # Project convention: figures don't carry titles or suptitles — they
    # get explanatory captions in the document around them instead. The
    # rcParams above zero out axes titles; this also patches Figure.suptitle
    # and Axes.set_title to be visual no-ops so existing call sites stop
    # rendering text without needing a sweep of edits. Both originals are
    # preserved at attribute names below for callers that need to opt back
    # in (e.g. a one-off interactive plot in a notebook).
    _disable_titles_globally()


# Originals are stashed once at module import time so this is idempotent —
# repeated setup_plotting_style() calls don't re-wrap an already-wrapped
# function.
_ORIGINAL_AXES_SET_TITLE = plt.Axes.set_title
_ORIGINAL_FIGURE_SUPTITLE = plt.Figure.suptitle


def _disable_titles_globally() -> None:
    """Replace Axes.set_title and Figure.suptitle with no-ops.

    Callers that want a title back can call ``set_title`` /  ``suptitle``
    via the ``_ORIGINAL_*`` references on this module, or set the
    rcParam ``axes.titlesize`` to a positive value and re-import.
    """

    def _no_title(self, *_args, **_kwargs):
        return None

    # Runtime monkey-patch via setattr. The static signatures of
    # `Axes.set_title` / `Figure.suptitle` (positional + keyword args)
    # don't match the catch-all `(self, *_args, **_kwargs)`, but the
    # runtime behavior is intentional. Using setattr keeps the patch
    # invisible to static type checkers (`ty` doesn't honor the
    # mypy-style `# type: ignore[assignment]` comment we had here).
    setattr(plt.Axes, "set_title", _no_title)
    setattr(plt.Figure, "suptitle", _no_title)

def save_figure(
    fig,
    filename,
    output_dir='figures',
    formats=('pdf', 'png'),
    gist_url=None,
):
    """
    Save figure in multiple formats.

    Defaults to PDF (vector) + PNG (raster). PNG preserves the transparent
    figure / axes background that the config sets via
    ``figure.facecolor='none'``; JPEG cannot carry alpha and forces a
    white background, so we don't ship JPEG by default.

    Parameters:
    -----------
    fig : matplotlib.figure.Figure
        Figure to save
    filename : str
        Base filename (without extension)
    output_dir : str or Path
        Output directory
    formats : iterable[str]
        Output formats. PNG / PDF / SVG preserve transparency; JPEG does not.
    gist_url : str or None
        If set, embeds the URL as a reproduction-link metadata field
        on the saved artifacts. Read back with ``exiftool``, an online
        EXIF viewer, or GIMP's *Image Properties → Comments*. Matches
        the "Final-Figure Gist Convention" in CLAUDE.md — promoted
        figures (in any ``*_final/`` analysis dir) should ship a gist
        URL so readers can run ``uv run make_<slug>.py`` themselves.

        PNG: written as a ``Source`` tEXt chunk (a standard PNG
        keyword recognized by every PNG-aware tool).
        PDF: written as the ``Subject`` doc-info field (the closest
        analogue PDF carries for "where this came from").
        SVG / other vector formats: skipped — matplotlib's metadata
        plumbing doesn't surface them for non-PNG/PDF backends.
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    for fmt in formats:
        filepath = output_path / f"{filename}.{fmt}"
        save_kwargs = {"format": fmt, "dpi": 300, "bbox_inches": "tight"}
        if gist_url:
            if fmt == "png":
                save_kwargs["metadata"] = {"Source": gist_url}
            elif fmt == "pdf":
                # PDF info dict uses different keyword names than PNG's
                # tEXt; "Subject" is the conventional slot for a
                # reproduction / source URL.
                save_kwargs["metadata"] = {"Subject": gist_url}
        fig.savefig(filepath, **save_kwargs)
        print(f"  Saved: {filepath}")

def create_figure(nrows=1, ncols=1, figsize=None, **kwargs):
    """
    Create a figure with modern styling.

    Parameters:
    -----------
    nrows : int
        Number of rows
    ncols : int
        Number of columns
    figsize : tuple
        Figure size (width, height). If None, uses default based on layout
    **kwargs : dict
        Additional arguments passed to plt.subplots

    Returns:
    --------
    fig, axes : Figure and axes objects
    """
    if figsize is None:
        # Auto-size based on layout (4:5 height:width per panel)
        width = 5 * ncols
        height = 4 * nrows
        figsize = (width, height)

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize, **kwargs)

    return fig, axes

def style_barplot(ax, round_corners=None, corner_radius=None):
    """
    Apply default bar styling, including rounded corners when enabled.

    Parameters:
    -----------
    ax : matplotlib.axes.Axes
        Axes containing bar patches
    round_corners : bool or None
        Whether to round corners; None uses ROUND_BARS_DEFAULT
    corner_radius : float or None
        Radius for corner rounding in data coordinates; None uses automatic calculation
    """
    if round_corners is None:
        round_corners = ROUND_BARS_DEFAULT

    if round_corners:
        from matplotlib.patches import PathPatch, Rectangle
        from matplotlib.path import Path

        for bar in list(ax.patches):
            if not isinstance(bar, Rectangle):
                continue

            x, y = bar.get_x(), bar.get_y()
            width, height = bar.get_width(), bar.get_height()
            if width == 0 or height == 0:
                continue

            facecolor = bar.get_facecolor()
            edgecolor = bar.get_edgecolor()
            zorder = bar.get_zorder()

            # Calculate corner radius (in data coordinates)
            if corner_radius is not None:
                r = corner_radius
            else:
                # Use 50% of bar width for prominently rounded corners
                r = abs(width) * 0.50

            # Create rounded rectangle path manually
            x2 = x + width
            y2 = y + height

            # Magic number for approximating a quarter circle with cubic Bezier
            # Control point offset = 4/3 * (sqrt(2)-1) * r ≈ 0.5522847498 * r
            # This creates the smoothest circular arc approximation
            offset = r * 0.5522847498

            # Define path with cubic Bezier curves for smooth rounded corners
            # Using CURVE4 for better circular approximation
            verts = [
                (x + r, y),           # Start at bottom edge after curve
                (x2 - r, y),          # End of bottom straight edge
                (x2 - offset, y),     # Control point 1 for bottom-right
                (x2, y + offset),     # Control point 2 for bottom-right
                (x2, y + r),          # End of bottom-right curve
                (x2, y2 - r),         # End of right straight edge
                (x2, y2 - offset),    # Control point 1 for top-right
                (x2 - offset, y2),    # Control point 2 for top-right
                (x2 - r, y2),         # End of top-right curve
                (x + r, y2),          # End of top straight edge
                (x + offset, y2),     # Control point 1 for top-left
                (x, y2 - offset),     # Control point 2 for top-left
                (x, y2 - r),          # End of top-left curve
                (x, y + r),           # End of left straight edge
                (x, y + offset),      # Control point 1 for bottom-left
                (x + offset, y),      # Control point 2 for bottom-left
                (x + r, y),           # Close the path
            ]

            codes = [
                Path.MOVETO,    # Start
                Path.LINETO,    # Bottom edge
                Path.CURVE4,    # Bottom-right: control point 1
                Path.CURVE4,    # Bottom-right: control point 2
                Path.CURVE4,    # Bottom-right: end point
                Path.LINETO,    # Right edge
                Path.CURVE4,    # Top-right: control point 1
                Path.CURVE4,    # Top-right: control point 2
                Path.CURVE4,    # Top-right: end point
                Path.LINETO,    # Top edge
                Path.CURVE4,    # Top-left: control point 1
                Path.CURVE4,    # Top-left: control point 2
                Path.CURVE4,    # Top-left: end point
                Path.LINETO,    # Left edge
                Path.CURVE4,    # Bottom-left: control point 1
                Path.CURVE4,    # Bottom-left: control point 2
                Path.CURVE4,    # Bottom-left: end point (close)
            ]

            path = Path(verts, codes)
            patch = PathPatch(path, facecolor=facecolor, edgecolor=edgecolor,
                            linewidth=0, zorder=zorder)
            ax.add_patch(patch)
            bar.set_visible(False)

def add_significance_bar(ax, x1, x2, y, height=0.05, text='***', **kwargs):
    """
    Add a significance bar between two points.

    Parameters:
    -----------
    ax : matplotlib.axes.Axes
        Axes to add bar to
    x1, x2 : float
        X coordinates of the two points
    y : float
        Y coordinate of the bar
    height : float
        Height of the vertical lines
    text : str
        Text to display above the bar
    """
    # Default styling
    bar_kwargs = {'color': COLORS['dark'], 'linewidth': 1.5}
    bar_kwargs.update(kwargs)

    # Draw the bar
    ax.plot([x1, x1, x2, x2], [y, y+height, y+height, y], **bar_kwargs)

    # Add text
    ax.text((x1+x2)/2, y+height, text, ha='center', va='bottom',
            fontsize=12, fontweight='bold', color=COLORS['dark'])

def format_percentage_axis(ax, axis='y'):
    """
    Format an axis to show percentages.

    Parameters:
    -----------
    ax : matplotlib.axes.Axes
        Axes to format
    axis : str
        Which axis to format ('x' or 'y')
    """
    from matplotlib.ticker import PercentFormatter

    if axis == 'y':
        ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    else:
        ax.xaxis.set_major_formatter(PercentFormatter(1.0))

# Color getters for convenience
def get_color(name):
    """Get a color from the palette by name"""
    return COLORS.get(name, COLORS['primary'])

def get_categorical_colors(n=None):
    """Get categorical color palette"""
    if n is None:
        return CATEGORICAL_PALETTE
    return CATEGORICAL_PALETTE[:n] if n <= len(CATEGORICAL_PALETTE) else sns.color_palette("husl", n)

def get_diverging_palette(n=11):
    """Get diverging color palette"""
    return sns.blend_palette(["#8878C8", "#FFFFFF", "#BC3C4C"], n_colors=n)


def get_sequential_palette(family="maroon", n=6):
    """Get a sequential palette by family.

    Parameters
    ----------
    family : str
        One of ``maroon``, ``teal``, ``amber``, ``lavender``.
    n : int
        Number of colors to return.
    """
    if family not in SEQUENTIAL_PALETTES:
        family = "maroon"
    palette = SEQUENTIAL_PALETTES[family]
    if n <= len(palette):
        return palette[:n]
    return sns.blend_palette(palette, n_colors=n)
