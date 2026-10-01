from __future__ import annotations

from dataclasses import dataclass

from .manifest import BASELINE, DUELPTS_V13_SHA256


@dataclass(frozen=True)
class VisualRegression:
    name: str
    component: str
    member: str
    expected_sha256: str
    note: str


VISUAL_REGRESSIONS = (
    VisualRegression(
        "CHANGE TURN clipping",
        "TCHANGE.IMG",
        "STRIG_IMG_TCHANGE_TGA",
        BASELINE.component("TCHANGE.IMG").v13.sha256,
        "CHANGE occupies the retail top row and TURN the retail lower row.",
    ),
    VisualRegression(
        "Deck Builder ACE badge",
        "DECK.DAT",
        "DECK_SRC_DC_P02_TGA",
        BASELINE.component("DECK.DAT").v13.sha256,
        "Only the former 切 badge region is changed to ACE.",
    ),
    VisualRegression(
        "Duel digits 6-9",
        "DUELPTS.DAT",
        "DUELPTS_SRC_G_P00_TGA",
        DUELPTS_V13_SHA256,
        "LEFT begins below the shared numeric strip; digits 6-9 retain clean retail pixels.",
    ),
)
