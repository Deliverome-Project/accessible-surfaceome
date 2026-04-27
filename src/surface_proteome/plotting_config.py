"""
Modern plotting configuration for the internalizers project.

Uses seaborn styling with custom colors and fonts for publication-quality figures.
"""
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Modern color palette - professional and accessible
COLORS = {
    'primary': '#DD5955',      # Warm coral
    'secondary': '#3469CD',    # Strong blue
    'accent': '#FFD579',       # Warm gold
    'success': '#749C75',      # Sage green
    'warning': '#DD5955',      # Coral (match primary for alerts)
    'accent_blue': '#3469CD',  # Accent blue
    'accent_gold': '#FFD579',  # Warm gold
    'accent_green': '#749C75', # Sage green
    'neutral': '#6C757D',      # Gray
    'light': '#E9ECEF',        # Light gray
    'dark': '#5E5E5E',         # Dark gray
}

# Extended palette for categorical data
CATEGORICAL_PALETTE = [
    '#DD5955',  # Primary
    '#3469CD',  # Secondary
]

# Diverging palette (for showing differences)
DIVERGING_PALETTE = sns.color_palette("RdBu_r", n_colors=11)

# Default bar styling configuration
ROUND_BARS_DEFAULT = False

def setup_plotting_style(style='default', context='notebook', font_scale=2.2):
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

    # Set seaborn style
    if style == 'default':
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

        # Font
        'font.family': 'sans-serif',
        'font.sans-serif': ['Space Grotesk', 'DM Sans', 'DejaVu Sans', 'Liberation Sans', 'Arial'],
        'font.size': 11,

        # Axes
        'axes.labelsize': 12,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.labelweight': 'normal',
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': True,
        'axes.axisbelow': True,
        'axes.edgecolor': COLORS['neutral'],
        'axes.labelcolor': COLORS['dark'],
        'axes.facecolor': 'none',
        'text.color': COLORS['dark'],

        # Grid
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
        'grid.linewidth': 0.8,

        # Ticks
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'xtick.color': COLORS['dark'],
        'ytick.color': COLORS['dark'],

        # Legend
        'legend.frameon': True,
        'legend.framealpha': 0.9,
        'legend.fancybox': True,
        'legend.fontsize': 10,

        # Lines
        'lines.linewidth': 2,
        'lines.markersize': 8,

        # Patches (bars, etc.)
        'patch.edgecolor': 'none',
        'patch.linewidth': 0.0,
    })

    print("OK Plotting style configured")

    # Default despine to top/right for a clean look.
    sns.despine(top=True, right=True)

def save_figure(fig, filename, output_dir='figures', formats=['pdf', 'jpeg']):
    """
    Save figure in multiple formats.

    Parameters:
    -----------
    fig : matplotlib.figure.Figure
        Figure to save
    filename : str
        Base filename (without extension)
    output_dir : str or Path
        Output directory
    formats : list
        List of formats to save ('png', 'pdf', 'svg')
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    for fmt in formats:
        filepath = output_path / f"{filename}.{fmt}"
        fig.savefig(filepath, format=fmt, dpi=300, bbox_inches='tight')
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
    return sns.color_palette("RdBu_r", n_colors=n)

# Initialize on import
setup_plotting_style()
