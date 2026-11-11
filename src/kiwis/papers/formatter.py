"""Result table formatting utilities."""


def format_results_table(
    methods: list[str],
    metrics: dict[str, list[float]],
    metric_names: list[str] | None = None,
) -> str:
    """Format experiment results as a LaTeX table.
    
    Args:
        methods: List of method names (rows)
        metrics: Dict mapping metric name to list of values per method
        metric_names: Optional custom column headers
    
    Returns:
        LaTeX tabular code
    """
    if not methods:
        return ""

    num_methods = len(methods)
    
    # Default metric names (use the first 5 metrics available)
    metric_keys = list(metrics.keys())[:5]
    if not metric_names:
        metric_names = metric_keys
    
    # Calculate best values per metric (bold formatting)
    best_values = {}
    for metric_key in metric_keys:
        values = metrics.get(metric_key, [])
        if values:
            # Assume higher is better
            max_val = max(values)
            best_values[metric_key] = max_val
    
    lines = []
    # Table header
    header_cols = ["Method"] + [m.replace("_", "\\_") for m in metric_names]
    lines.append("\\begin{{table}}[ht]")
    lines.append("\\centering")
    lines.append(f"\\begin{{tabular}}{{l{ "c" * len(metric_names)}}}")
    lines.append("\\toprule")
    lines.append(" & ".join(header_cols) + "\\\\ \\midrule")
    
    # Table rows
    for i, method in enumerate(methods):
        row_cells = [method]
        for j, metric_key in enumerate(metric_keys):
            values = metrics.get(metric_key, [])
            if i < len(values):
                val = f"{values[i]:.4f}"
                # Bold the best value per column
                if metric_key in best_values and abs(values[i] - best_values[metric_key]) < 1e-6:
                    val = f"\\textbf{{{val}}}"
                row_cells.append(val)
            else:
                row_cells.append("-")
        lines.append(" & ".join(row_cells) + "\\\\ \\hline")
    
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\caption{Comparison of methods on key metrics. Best values in bold.}")
    lines.append("\\end{table}")
    
    return "\n".join(lines)


def format_ablation_table(methods: list[str], results_dict: dict[str, float]) -> str:
    """Format an ablation study table."""
    lines = ["\\begin{table}[ht]", "\\centering", "\\begin{tabular}{l c}", "\\toprule"]
    lines.append("Variant & Result \\\\\\ \\midrule")
    
    for method in methods:
        result_val = results_dict.get(method, 0.0)
        if isinstance(result_val, float):
            lines.append(f"{method} & {result_val:.4f} \\\\ \\hline")
        else:
            lines.append(f"{method} & {str(result_val)} \\\\ \\hline")
    
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\caption{Ablation study results.}")
    lines.append("\\end{table}")
    
    return "\n".join(lines)
