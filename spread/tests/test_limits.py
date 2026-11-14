"""Tests of the note's own limits: its deadline and the hours of the sites, and what the desk does with them."""
from __future__ import annotations

from spreadlab import notes
from test_harness import desk, request

DAY = 1440


def limits(text: str, arrived_at: int = 500) -> notes.Limits:
    return notes.limits({"text": text}, arrived_at)


def test_a_note_gives_a_deadline_for_the_delivery():
    assert limits("Moi. Pitää olla perillä huomenna 17 mennessä!").deadline == DAY + 17 * 60
    assert limits("At destination Monday 13:30 latest. Call the customer an hour before arrival.").deadline == 7 * DAY + 13 * 60 + 30  # the request came on a Monday
    assert limits("asiakas tulee hakemaan, perillä viim. klo 13").deadline == 13 * 60
    assert limits("Customer picks it up tomorrow 4pm, must be there by then. Thanks").deadline == DAY + 16 * 60
    assert limits("Hejsan. Ska vara på plats senast imorgon 12, inte 11:00! Öppet vardagar 8-19.") == notes.Limits(DAY + 12 * 60, (8 * 60, 19 * 60))
    assert limits("Must be at destination by tomorrow 15:00, sorry, I mean 14:00").deadline == DAY + 14 * 60
    assert limits("Toimitus perille viim. ti klo 20, eikun ke!").deadline == 2 * DAY + 20 * 60
    assert limits("Not ready before tomorrow 7:00. Key box code 3745") == notes.Limits()  # when the car is ready is not a limit
    assert limits("Soita asiakkaalle 15 min ennen") == notes.Limits()


def test_a_note_gives_the_hours_of_the_pickup_site_or_of_the_delivery_site():
    assert limits("we close at 14:30.").pickup_hours == (0, 14 * 60 + 30)
    assert limits("Liike kiinni klo 15.30, haettava ennen sitä. Noudettavissa aikaisintaan perjantaina klo 9.00.").pickup_hours == (0, 15 * 60 + 30)
    assert limits("Pickup weekdays 9:00-17:00 only. Call the customer an hour before arrival.") == notes.Limits(0, (9 * 60, 17 * 60))
    assert limits("haettava ennen kahta. odottaa osia, valmis huomenna klo 7").pickup_hours == (0, 14 * 60)
    assert limits("Vi stänger kl 17, nej förlåt, kl 18").pickup_hours == (0, 18 * 60)
    assert limits("haettava ennen klo 20. auto valmis vasta huomenna klo 8, ei kun klo 9").pickup_hours == (0, 20 * 60)  # the correction is of the ready time
    assert limits("destination closes at 16:00, car is ready and waiting") == notes.Limits(0, (0, 0), (0, 16 * 60))
    assert limits("Perillä ei ketään 15 jälkeen").delivery_hours == (0, 15 * 60)
    assert limits("toimitukset vastaanotetaan puoli viiteen asti, kiitos taas").delivery_hours == (0, 16 * 60 + 30)
    assert limits("Vastaanottava liike auki arkipäivisin 10–16.").delivery_hours == (10 * 60, 16 * 60)
    assert limits("Receiving until 17:00 only. Correction: 18:00. Car in bay 16, keys at the desk.").delivery_hours == (0, 18 * 60)
    assert limits("Seller home 16:15-19:15. Receiving until 16:30 only").delivery_hours == (0, 16 * 60 + 30)  # a slot of three hours is not opening hours


def won(d, note: str, deadline: int = 2640, last_pickup: int = 2520, **more) -> dict:
    """Quotes and wins a request with this note, and returns the post."""
    q = request("R1", note={"text": note}, **more)
    d.quote(q)
    d.win({"id": "R1", "legs": q["legs"], "deliveredAt": [None], "deadline": deadline, "option": "next_day", "lastPickupAt": last_pickup})
    return d.outbox[-1]


def windows(post: dict) -> dict:
    return {stop["kind"]: stop.get("window") for stop in post["stops"]}


def test_the_desk_books_and_posts_an_order_by_the_deadline_of_its_note():
    d = desk(read_notes=True, note_limits=True, fee=1.0)
    post = won(d, "Perillä huomenna klo 12 mennessä")  # 2160, eight hours before the order's deadline; the drive takes 120 minutes
    assert d.orders["R1"]["deadline"] == 2160 and d.orders["R1"]["lastPickupAt"] == 2040
    assert windows(post) == {"pickup": None, "delivery": {"from": 500, "to": 2160}}
    plain = desk(read_notes=True, fee=1.0)
    won(plain, "Perillä huomenna klo 12 mennessä")
    assert plain.orders["R1"]["deadline"] == 2640  # off at its default
    # At the quote an option ends at the note's deadline: by 13:00 today leaves 145 minutes to find a driver.
    both = desk(read_notes=True, note_limits=True, same_day=True), desk(read_notes=True, same_day=True)
    for d_ in both:
        d_.quote(request("R3", note={"text": "perillä viim. klo 13"}, options=(("same_day", 1200),)))
    assert both[0].decisions["R3"]["declined"] == "slack" and both[1].decisions["R3"]["declined"] is None


def test_a_site_with_hours_in_the_note_gets_its_stops_on_one_day_and_the_next_day_when_the_gig_expires():
    d = desk(read_notes=True, note_limits=True, fee=1.0)
    post = won(d, "We close at 14:30. Key box code 3745")
    assert windows(post) == {"pickup": {"from": 500, "to": 869}, "delivery": {"from": 500, "to": DAY - 1}}  # a visit at the closing minute fails
    d.read_results([post], [{"ok": True, "id": "G1"}])
    d.now, d.outbox = 871, []
    d.handle({"kind": "gig_expired", "gigId": "G1", "at": 871})
    assert windows(d.outbox[-1]) == {"pickup": {"from": DAY, "to": DAY + 869}, "delivery": {"from": DAY, "to": 2640}} and d.unbooked() == 1
    d.read_results(d.outbox[-1:], [{"ok": True, "id": "G2"}])
    d.now, d.outbox = 2 * DAY + 600, []  # past the last minute that still makes the deadline: the pickup still goes while the site is open
    d.handle({"kind": "gig_expired", "gigId": "G2", "at": 2 * DAY + 600})
    assert windows(d.outbox[-1]) == {"pickup": {"from": 2 * DAY + 600, "to": 2 * DAY + 869}, "delivery": None}
    # The delivery site's hours move the pickup too: it closes at 16:00 and the drive takes 120 minutes.
    d = desk(read_notes=True, note_limits=True, fee=1.0)
    assert windows(won(d, "Destination closes at 16:00")) == {"pickup": {"from": 500, "to": 839}, "delivery": {"from": 500, "to": 959}}
    # A drive too long to deliver before the site closes that day: the pickup alone goes by its site's hours.
    d = desk(read_notes=True, note_limits=True, fee=1.0)
    d.minutes = {key: 700 for key in d.minutes}
    assert windows(won(d, "Pickup weekdays 9:00-15:00 only. Destination closes at 16:00", deadline=4000, last_pickup=3300)) == {"pickup": {"from": 540, "to": 899}, "delivery": None}
