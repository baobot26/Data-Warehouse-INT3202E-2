import argparse

from etl.etl_legacy import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the layered MongoDB to Bronze/Silver/Gold ETL pipeline."
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Accepted for compatibility; each layered run creates a new batch.",
    )
    parser.parse_args()

    run_pipeline()


if __name__ == "__main__":
    main()
