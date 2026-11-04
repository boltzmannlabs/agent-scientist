"""Recoverable source loading for the saved-specialist editor."""
from dataclasses import replace
from agent.specialist_sources import instruction_fields, load_reference


def purpose_fields(ui, *, current=None, initial=None):
    value = initial
    while True:
        if value is None:
            value = ui.ask('What should this specialist do, and when? Enter text or an instruction Markdown file path:' +
                           (' (blank keeps current)' if current is not None else ''), allow_blank=current is not None)
        if not value.strip() and current is not None:
            return {'purpose': current}
        try:
            fields = instruction_fields(value)
            if fields.get('instruction_source'):
                ui.show(f'Loaded instruction file: {fields["instruction_source"]} '
                        f'({len(fields["instructions"])} characters). Its full contents are saved as instructions; '
                        'review them below. No model request was made.')
            return fields
        except (ValueError, OSError, UnicodeError) as exc:
            ui.show(f'Could not read instruction file: {exc}. Try text or another path; previous answers are retained.')
            value = None


def prepare_references(item, ui, *, refresh=False):
    documents = [] if refresh else list(item.source_documents)
    if item.source_manifest and not refresh:
        from agent.specialist_source_library import library_documents
        documents.extend(library_documents(item.source_manifest))
    documents = [doc for doc in documents if doc['source'] in item.sources]
    known = {doc['source'] for doc in documents}
    for source in item.sources:
        if source in known:
            continue
        ui.show(f'Reading reference: {source}. Readable text will be saved and supplied to this profile’s '
                'selected model on specialist assignments. No scripts or scientific tools are run.')
        warnings = []
        documents.extend({**doc, 'source': source} for doc in load_reference(source, warnings=warnings))
        for message in warnings:
            ui.show(message)
    if sum(len(doc['text']) for doc in documents) > 40_000 or len(documents) > 20:
        from agent.specialist_source_library import store_library
        prepared = replace(item, source_documents=(), source_manifest=store_library(documents))
        ui.show(f'Reference library: {len(documents)} documents. Relevant snapshots are read on demand; '
                'the complete collection is not placed into every model request.')
    else:
        prepared = replace(item, source_documents=tuple(documents), source_manifest='')
    from dataclasses import asdict
    from agent.specialist_store import Specialist
    return Specialist.parse(asdict(prepared))
