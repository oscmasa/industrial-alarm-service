import pytest

from alarm_service.application.normalization.service import normalize_record
from alarm_service.domain.catalog import CSV_FIELDS
from alarm_service.infrastructure.files.csv_reader import CsvSourceError, iter_csv_records


def test_bom_and_embedded_newline_use_record_numbers(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text(
        ",".join(CSV_FIELDS) + "\nEVT-00000001,2026-09-15T14:32:10,PUMP_01_FLOW,LOW_FLOW,HIGH,"
        '"line one\nline two",12.5\n',
        encoding="utf-8-sig",
        newline="",
    )
    records = list(iter_csv_records(path))
    assert len(records) == 1 and records[0][0] == 1
    assert normalize_record(records[0][1]).alarm.message == "line one\nline two"


@pytest.mark.parametrize("header", ["", "a,b,c\n", ",".join(CSV_FIELDS[:-1] + ("message",)) + "\n"])
def test_bad_headers_fail_at_file_level(tmp_path, header):
    path = tmp_path / "source.csv"
    path.write_text(header, encoding="utf-8")
    with pytest.raises(CsvSourceError):
        list(iter_csv_records(path))


def test_bad_row_counts_are_row_level_errors(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text(
        ",".join(CSV_FIELDS) + "\nonly,three,values\na,b,c,d,e,f,g,h\n", encoding="utf-8"
    )
    results = [normalize_record(row) for _, row in iter_csv_records(path)]
    assert len(results) == 2
    assert all(result.errors[0].code == "MALFORMED_ROW" for result in results)


def test_unreadable_csv_fails_at_file_level(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text(",".join(CSV_FIELDS) + '\n"unfinished', encoding="utf-8")
    with pytest.raises(CsvSourceError):
        list(iter_csv_records(path))
