"""Publication-quality visualization functions."""

from __future__ import annotations

import os
from typing import Optional


def save_figure(fig, filename: str = "figure.png", dpi: int = 300) -> str:
    """Save a matplotlib figure to disk in multiple formats."""
    base, _ = os.path.splitext(filename)
    
    # PNG (publication-ready)
    png_path = f"{base}.png"
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    
    # SVG (vector for editing)
    svg_path = f"{base}.svg"
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    
    return png_path


def create_comparison_bar_chart(
    methods: list[str],
    values: dict[str, list[float]],
    title: str = "Method Comparison",
    metric_name: str = "Value",
    y_min: float | None = None,
    y_max: float | None = None,
) -> "matplotlib.figure.Figure":
    """Create a publication-quality bar chart comparing methods."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    n_methods = len(methods)
    x = np.arange(n_methods)
    width = 0.6
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Colorblind-friendly palette
    colors = plt.cm.Set2(np.linspace(0, 1, max(len(values), n_methods)))
    
    for i, (metric_key, metric_vals) in enumerate(values.items()):
        if len(metric_vals) >= n_methods:
            ax.bar(x + i * width / len(values), metric_vals[:n_methods], 
                   width=width / max(len(values), 1), label=metric_key, color=colors[i])
    
    if y_min is not None or y_max is not None:
        ax.set_ylim(y_min or 0, y_max or 1.0)
    
    ax.set_xticks(x + width / (max(len(values), 1) * 2))
    ax.set_xticklabels(methods, rotation=30, ha="right")
    ax.set_ylabel(metric_name)
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    
    # Style for publication
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    
    plt.tight_layout()
    return fig


def create_learning_curve_plot(
    epochs: list[int],
    train_losses: list[float],
    val_losses: list[float] | None = None,
    title: str = "Learning Curves",
) -> "matplotlib.figure.Figure":
    """Plot training/val learning curves."""
    import matplotlib.pyplot as plt
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Loss curves
    ax1.plot(epochs, train_losses, "b-", linewidth=2, label="Train Loss")
    if val_losses:
        ax1.plot(epochs, val_losses, "r--", linewidth=2, label="Val Loss")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title(title)
    ax1.legend()
    ax1.grid(alpha=0.3)
    
    # Accuracy curves (simulated if val_losses provided)
    if val_losses:
        import numpy as np
        val_acc = [1 - l for l in val_losses]  # Simple conversion
        train_acc = [1 - l for l in train_losses]
        
        ax2.plot(epochs, train_acc, "b-", linewidth=2, label="Train Acc")
        ax2.plot(epochs, val_acc, "r--", linewidth=2, label="Val Acc")
        ax2.set_xlabel("Epoch")
        ax2.set_ylabel("Accuracy")
        ax2.legend()
        ax2.grid(alpha=0.3)
    
    plt.tight_layout()
    return fig


def create_heatmap_visualization(
    data: list[list[float]],
    labels_x: list[str] | None = None,
    labels_y: list[str] | None = None,
    title: str = "Confusion Matrix",
    vmin: float | None = None,
    vmax: float | None = None,
) -> "matplotlib.figure.Figure":
    """Create a heatmap visualization (e.g., confusion matrix)."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    array = np.array(data)
    cax = ax.imshow(array, cmap="viridis", vmin=vmin, vmax=vmax, aspect="auto")
    
    if labels_x:
        ax.set_xticks(range(len(labels_x)))
        ax.set_xticklabels(labels_x, rotation=45, ha="right")
    if labels_y:
        ax.set_yticks(range(len(labels_y)))
        ax.set_yticklabels(labels_y)
    
    # Add value annotations
    for i in range(array.shape[0]):
        for j in range(array.shape[1]):
            val = array[i, j]
            text_color = "white" if val > np.median(array.flatten()) else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color=text_color)
    
    plt.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    return fig


def create_boxplot_figure(
    data: dict[str, list[float]],
    title: str = "Result Distributions",
    metric_name: str = "Score",
) -> "matplotlib.figure.Figure":
    """Create boxplots comparing result distributions across methods."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    dataset = [v for v in data.values() if v]
    labels = list(data.keys())
    
    bp = ax.boxplot(dataset, labels=labels, patch_artist=True)
    
    # Color the boxes
    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_ylabel(metric_name)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
    
    plt.tight_layout()
    return fig
