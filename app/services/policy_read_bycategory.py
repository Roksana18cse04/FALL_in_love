import pandas as pd
import plotly.express as px
from app.config import CATEGORY_CSV
import matplotlib.pyplot as plt
import pandas as pd

import matplotlib.cm as cm
import numpy as np
from app.config import CATEGORY_CSV
def show_category_view_graph():
    df = pd.read_csv(CATEGORY_CSV)
    df = df.sort_values(by="view_count", ascending=False)

    fig = px.bar(
        df,
        x="category",
        y="view_count",
        title="Policy Read Rate by Category",
        color="category",
        text="view_count"
    )

    fig.update_layout(xaxis_title="Category", yaxis_title="View Count")
    fig.show()

# Example call
show_category_view_graph()


def show_category_read_rate_bar():
    df = pd.read_csv(CATEGORY_CSV)

    # Total views across all categories
    total_views = df['view_count'].sum()

    # Normalize to percentage of 100 people
    df['percentage'] = round((df['view_count'] / total_views) * 100, 2)

    # Sort by percentage
    df = df.sort_values(by='percentage', ascending=False)

    # Get unique categories
    unique_cats = df['category'].unique()
    n = len(unique_cats)

    # Generate a color map with n distinct colors from 'tab20' or 'Set3' or 'viridis'
    colormap = cm.get_cmap('tab20', n)  # You can change 'tab20' to any matplotlib colormap

    # Map each category to a color
    color_map = {cat: colormap(i) for i, cat in enumerate(unique_cats)}

    # Assign colors to bars based on category
    bar_colors = df['category'].map(color_map)

    # Plot
    plt.figure(figsize=(10, 6))
    bars = plt.bar(df['category'], df['percentage'], color=bar_colors)
    plt.title("📊 Policy View Rate by Category (Normalized to 100 People)", fontsize=14)
    plt.xlabel("Policy Category", fontsize=12)
    plt.ylabel("Read Rate (%)", fontsize=12)
    plt.xticks(rotation=30)
    plt.ylim(0, 100)

    # Add % labels on top
    for bar in bars:
        height = bar.get_height()
        plt.annotate(f'{height:.1f}%',
                     xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 5),
                     textcoords="offset points",
                     ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    plt.show()

# Example usage
show_category_read_rate_bar()
