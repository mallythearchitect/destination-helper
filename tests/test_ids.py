from engine.ids import uuid7


def test_ids_sort_in_the_order_they_were_made():
    ids = [uuid7() for _ in range(5000)]
    assert ids == sorted(ids) and len(set(ids)) == 5000
    assert all(i[14] == "7" and i[19] in "89ab" for i in ids)
