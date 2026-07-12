"""RATD runtime rebuilt against RATD_Memory_Circuit_Spec.md v1.0.

Control plane (circuit): pins, gates, agent nodes, wiring — enumerable
structure, nothing free-form. Data plane (memory): catalog (mechanical
shadow of the circuit) + write-once store. They touch at exactly one
directed edge: a write fulfills a pin.

Modules:
- addresses: A1 grammar (one syntax, enforced everywhere, never relaxed)
- circuit:   A2 pins/lifecycle, B1 gates, B3 provenance, B4 liveness,
             B5 quiescence + failure predicate, B7 agent statechart
- store:     A3 write-once entries, A4 open-read + fetch log,
             A5 structured entries / bounded list+fetch, A6 catalog
- validate:  action documents + B2 wiring validity (hard reject)
- doctor:    C1-C5 (dossier, privileges, accounting)
- runtime:   the sequential loop (A'1 snapshot-at-dequeue, A'3
             interleaving record; parallel runtime itself is Part D)
"""
