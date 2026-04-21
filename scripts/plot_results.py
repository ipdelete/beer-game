import sys

# Try to import visualization libraries; fail gracefully if missing
try:
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError:
    print("Missing pandas or matplotlib. Please run: pip install pandas matplotlib")
    sys.exit(1)

import argparse


def plot_results(files):
    plt.figure(figsize=(14, 10))

    roles = ["Retailer", "Wholesaler", "Distributor", "Factory"]
    colors = {"mechanistic": "blue", "gabm": "green"}

    for file in files:
        # derive mode from filename if possible, otherwise provided as arg
        mode = "gabm" if "gabm" in file.lower() else "mechanistic"
        df = pd.read_csv(file)

        for i, role in enumerate(roles):
            role_df = df[df["Role"] == role]
            plt.subplot(2, 2, i + 1)
            plt.plot(
                role_df["Turn"],
                role_df["Order"],
                label=f"{mode} Order",
                color=colors[mode],
                marker="o",
            )
            plt.title(f"{role} Behavior")
            plt.xlabel("Turn")
            plt.ylabel("Cases")
            plt.legend()

    plt.tight_layout()
    plt.savefig("bullwhip_comparison.png")
    print("Visualization saved to bullwhip_comparison.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="CSV files to compare")
    args = parser.parse_args()

    plot_results(args.files)
