"""Docker entrypoint for the layered warehouse ETL."""

from etl.etl_legacy import run_pipeline


def run_etl() -> None:
    run_pipeline()


if __name__ == "__main__":
    run_etl()
