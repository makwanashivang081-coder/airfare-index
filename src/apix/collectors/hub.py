from apix.collectors.fixture_adapter import FixtureAdapter
from apix.common.exceptions import ContractError
from apix.source_registry.service import Source


class AdapterHub:
    """Hub-and-spoke: fixture by default; live adapters when allow_http is true."""

    def adapter_for(self, source: Source):
        if source.allow_http:
            if source.id == "SRC-MMT":
                from apix.collectors.live.mmt import MakeMyTripPublicAdapter

                return MakeMyTripPublicAdapter(source.id)
            if source.id == "SRC-IXIGO":
                from apix.collectors.live.ixigo import IxigoMarketAdapter

                return IxigoMarketAdapter(source.id)
            if source.id == "SRC-GFL":
                from apix.collectors.live.google_flights import GoogleFlightsMarketAdapter

                return GoogleFlightsMarketAdapter(source.id)
            if source.id == "SRC-CLEARTRIP":
                from apix.collectors.live.cleartrip import CleartripMarketAdapter

                return CleartripMarketAdapter(source.id)
            code = (source.airline_code or "").upper()
            if code == "SG":
                from apix.collectors.live.spicejet import SpiceJetLiveAdapter

                return SpiceJetLiveAdapter(source.id)
            if code == "6E":
                from apix.collectors.live.indigo import IndigoLiveAdapter

                return IndigoLiveAdapter(source.id)
            if code == "AI":
                from apix.collectors.live.air_india import AirIndiaLiveAdapter

                return AirIndiaLiveAdapter(source.id)
            if code == "QP":
                from apix.collectors.live.akasa import AkasaLiveAdapter

                return AkasaLiveAdapter(source.id)
            if code == "UK":
                from apix.collectors.live.vistara import VistaraLiveAdapter

                return VistaraLiveAdapter(source.id)
            raise ContractError(f"{source.id}: no live adapter for airline {code}")

        if source.adapter == "mmt_fixture":
            return FixtureAdapter(source.id, "6E")
        if source.adapter in {
            "ixigo_fixture",
            "google_flights_fixture",
            "cleartrip_fixture",
        }:
            return FixtureAdapter(source.id, "6E")
        if source.adapter == "dgca_reference":
            return FixtureAdapter(source.id, "AI")
        if source.adapter and source.airline_code and (
            source.adapter.endswith("_fixture") or source.adapter.endswith("_live")
        ):
            return FixtureAdapter(source.id, source.airline_code)
        raise ContractError(f"No adapter registered for {source.id}")

    def execute(self, source: Source, job):
        return self.adapter_for(source).search_fares(job)
