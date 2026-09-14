from apix.collectors.fixture_adapter import FixtureAdapter
from apix.common.exceptions import ContractError
from apix.source_registry.service import Source


class AdapterHub:
    def adapter_for(self, source: Source) -> FixtureAdapter:
        if source.allow_http:
            raise ContractError(f"{source.id} has HTTP enabled — live booking scrape is not permitted.")
        if source.adapter == "mmt_fixture":
            return FixtureAdapter(source.id, "6E")
        if source.adapter == "dgca_reference":
            return FixtureAdapter(source.id, "AI")
        if source.adapter and source.adapter.endswith("_fixture") and source.airline_code:
            return FixtureAdapter(source.id, source.airline_code)
        raise ContractError(f"No adapter registered for {source.id}")

    def execute(self, source: Source, job):
        return self.adapter_for(source).search_fares(job)
