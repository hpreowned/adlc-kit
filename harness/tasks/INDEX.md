# Golden tasks

30 tasks. Schema: `SCHEMA.md`. Run: `adlc eval --tier N`.

| id | repo | category | langs | tier | judge | federated | prompt |
|---|---|---|---|---|---|---|---|
| svc-001 | kestrel-services | literal | python | 1 | rubric |  | A customer screenshot shows the public API answering with "booking temporarily unavailable |
| svc-003 | kestrel-services | trace | python | 1 | rubric |  | I'm tidying the gateway's legacy/ package, which holds the old local pricing formula from  |
| svc-004 | kestrel-services | trace | python | 1 | rubric |  | Which of the gateway's calls to booking and pricing get retried automatically when they fa |
| svc-006 | kestrel-services | literal | python | 1 | rubric |  | What is the default timeout for the gateway's calls to booking and pricing, and which envi |
| svc-008 | kestrel-services | edit | python | 1 | tests |  | Booking now returns eta_confidence on shipments, but the gateway silently drops it before  |
| web-001 | kestrel-web | literal | typescript | 1 | rubric |  | Which environment variable turns on comparing quotes across all carriers in the web app, w |
| web-002 | kestrel-web | locate | typescript | 1 | rubric |  | Where in the web app is a user stopped from firing the reserve request twice by clicking t |
| web-003 | kestrel-web | trace | typescript | 1 | rubric |  | The money rounding helper in the web app has a known bug. Which parts of the UI actually s |
| web-004 | kestrel-web | trace | typescript | 1 | rubric |  | A user clicks Reserve and the backend answers 409. Walk me through what the web code does  |
| web-005 | kestrel-web | trace | typescript | 1 | rubric |  | On the quote page, when the pricing call for one carrier fails, how does that failure get  |
| web-009 | kestrel-web | edit | typescript | 1 | tests |  | The gateway is about to start sending eta_confidence on shipments (a number from 0 to 1, p |
| web-010 | kestrel-web | edit | typescript | 1 | tests |  | Our money rounding in the web app disagrees with the invoices: exact halves should round a |
| svc-002 | kestrel-services | locate | java | 2 | rubric |  | In the booking service, where does an incoming create or reserve request actually get rate |
| svc-009 | kestrel-services | edit | csharp | 2 | tests |  | The fuel surcharge in pricing rounds with plain Math.Round, which uses banker's rounding,  |
| svc-010 | kestrel-services | edit | java | 2 | tests |  | The shipments table has a foreign key to carriers, but the JPA Shipment entity only has a  |
| ops-001 | kestrel-ops | archaeology | docs | 3 | rubric |  | Why does booking keep a separate rate-limit bucket for each carrier instead of one simple  |
| ops-002 | kestrel-ops | archaeology | docs | 3 | rubric |  | Finance noticed a surcharge pricing at 10.12 on an invoice line but 10.13 on the carrier s |
| ops-003 | kestrel-ops | archaeology | docs | 3 | rubric |  | The booking schema enforces that every shipment points at a real carrier, but the Java ent |
| ops-004 | kestrel-ops | archaeology | docs | 3 | rubric |  | Our static analyzer flags LegacyTariffLoader in pricing as having zero references, and the |
| ops-005 | kestrel-ops | locate | docs | 3 | rubric |  | I'm on call and customers are getting "booking temporarily unavailable" on bookings. Which |
| ops-006 | kestrel-ops | locate | docs | 3 | rubric |  | Where are the contractual request limits for each carrier written down, what are they, and |
| ops-007 | kestrel-ops | literal | docs | 3 | rubric |  | In the ticket export CSV, what is the exact name of the column that says which team a tick |
| ops-008 | kestrel-ops | cross-project | docs | 3 | rubric | yes | Pricing wants to change the shape of the POST /v1/quote response. Which teams and consumer |
| ops-009 | kestrel-ops | cross-project | docs | 3 | rubric | yes | Who owns the decision to serialise concurrent reserves in booking with a database lock, an |
| ops-010 | kestrel-ops | cross-project | docs | 3 | rubric | yes | We want to add a column to the booking shipments table. Which teams must approve it, and w |
| svc-005 | kestrel-services | archaeology | java,docs | 3 | rubric | yes | BookingService.reserve() takes a lock keyed on the shipment reference before it even check |
| svc-007 | kestrel-services | cross-repo | java,python,typescript | 3 | rubric | yes | Which services and apps call booking's POST /v2/shipments, and what path does a browser re |
| web-006 | kestrel-web | cross-repo | typescript,python,java | 3 | rubric | yes | Booking started returning an ETA confidence score on shipments weeks ago, but the web app  |
| web-007 | kestrel-web | cross-repo | typescript,python,java | 3 | rubric | yes | The booking form generates a reference up front so that a double submit or a retry should  |
| web-008 | kestrel-web | cross-repo | typescript,python,java | 3 | rubric | yes | Will a shipment created from the web booking form actually be accepted by the real booking |

## By category

- archaeology: 5
- cross-project: 3
- cross-repo: 4
- edit: 5
- literal: 4
- locate: 4
- trace: 5
