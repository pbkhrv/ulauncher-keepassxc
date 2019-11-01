from time import sleep
import pytest
from keepassxc import keepassxc_db as kpdb


@pytest.fixture
def test_db():
    db = kpdb.KeepassxcDatabase()
    db.initialize("tests/data/test.kdbx", 0)
    return db


def test_unlock_wrong_passphrase(test_db):
    assert test_db.is_passphrase_needed()
    assert not test_db.verify_and_set_passphrase("wrong passphrase")


def test_unlock(test_db):
    assert test_db.is_passphrase_needed()
    assert test_db.verify_and_set_passphrase("right passphrase")


def test_db_not_found():
    db = kpdb.KeepassxcDatabase()
    with pytest.raises(kpdb.KeepassxcFileNotFoundError):
        db.initialize("test/data/no_such_file", 0)


def test_inactivity_lock():
    TIMEOUT = 1
    test_db = kpdb.KeepassxcDatabase()
    test_db.initialize("tests/data/test.kdbx", TIMEOUT)
    assert test_db.verify_and_set_passphrase("right passphrase")
    # dont need passphrase immediately after unlocking
    assert not test_db.is_passphrase_needed()
    # need passphrase again after waiting for more than the timeout
    sleep(TIMEOUT + 0.1)
    assert test_db.is_passphrase_needed()


def test_search_locked_db(test_db):
    with pytest.raises(kpdb.KeepassxcLockedDbError):
        test_db.search("none of this, you see")


def test_search_no_results(test_db):
    test_db.verify_and_set_passphrase("right passphrase")
    assert not test_db.search("none of this, you see")


def test_search(test_db):
    test_db.verify_and_set_passphrase("right passphrase")
    res = test_db.search("onlinesite")
    assert len(res) == 2
    assert "onlinesite personal" in res
    assert "onlinesite work" in res


def test_get_entry_details_locked_db(test_db):
    with pytest.raises(kpdb.KeepassxcLockedDbError):
        test_db.get_entry_details("onlinesite personal")


def test_get_entry_details(test_db):
    test_db.verify_and_set_passphrase("right passphrase")
    details = test_db.get_entry_details("onlinesite personal")
    assert details
    assert "UserName" in details and details["UserName"] == "username"
    assert "Password" in details and details["Password"] == "password"
    assert "URL" in details and details["URL"] == "url"
    assert "Notes" in details and details["Notes"] == "line1\nline2"


def test_lock_unlock_after_path_change(test_db):
    # unlock 1
    test_db.verify_and_set_passphrase("right passphrase")
    assert not test_db.is_passphrase_needed()
    # lock because path change
    test_db.change_path("tests/data/test2.kdbx")
    assert test_db.is_passphrase_needed()
    # unlock 2
    test_db.verify_and_set_passphrase("right passphrase2")
    assert not test_db.is_passphrase_needed()
