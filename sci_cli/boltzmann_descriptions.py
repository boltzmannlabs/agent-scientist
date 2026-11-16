"""Short catalog definitions, sourced from the maintained tool contracts."""
import json
import re

# Older contracts contain only a display label in their description field.
_LABEL_DEFINITIONS = {
    'Atom Mapping': 'Match corresponding atoms between reactants and products to help interpret a chemical reaction.',
    'Custom Property Model DL': 'Train a deep-learning model to predict molecular properties from your dataset.',
    'Custom Property Model ML': 'Train a machine-learning model to predict molecular properties from your dataset.',
    'Binding Site Prediction (fpocket)': 'Identify potential ligand-binding pockets in a protein structure using fpocket.',
    'Clean (Enzyme Classification)': 'Predict enzyme functional classifications from protein sequences using CLEAN.',
    'Condition Recommendation': 'Suggest reaction conditions for a supplied chemical transformation.',
    'Forward Reaction Prediction': 'Predict possible reaction products from the supplied reactants.',
    'Function-Based Enzyme Generation': 'Generate candidate enzyme sequences guided by a requested function.',
    'Impurity Prediction': 'Predict possible chemical impurities to support reaction review.',
    'K-Means Clustering': 'Group molecules into clusters based on their molecular representations.',
    'Lead Generation — Augmented': 'Generate candidate molecules with the augmented lead-generation workflow.',
    'Lead Generation — Reinvent': 'Generate candidate molecules with REINVENT and selected property objectives.',
    'Ligand MPNN': 'Design protein sequences with structural context from nearby ligands.',
    'Motif Scaffolding': 'Build candidate protein backbones around a supplied structural motif.',
    'NetsolP (Solubility)': 'Predict protein solubility from amino-acid sequences using NetSolP.',
    'Peptide Property Prediction': 'Estimate selected properties of peptide sequences.',
    'Pharmacophore Hypothesis (phcore_gen)': 'Identify a spatial arrangement of molecular features associated with ligand recognition.',
    'Pharmacophore Screening': 'Screen molecules for matches to a pharmacophore’s spatial feature pattern.',
    'Pharmacophore-Based Generator (pgmg_molgen)': 'Generate candidate molecules guided by a pharmacophore feature pattern.',
    'Property Prediction (propinf)': 'Predict selected molecular properties for compounds in an input library.',
    'R-Group Enumeration': 'Explore molecular variants by combining a scaffold with substituent groups.',
    'Random Controlled Mutagenesis': 'Create sequence variants within specified mutation constraints.',
    'Retrosynthesis': 'Suggest possible precursor molecules and reaction steps for a target compound.',
    'Similarity Screening': 'Find molecules similar to a reference compound in a molecular library.',
    'Structure-Based Peptide Generation': 'Generate candidate peptides using a target protein structure as context.',
    'Unconditional Sampling': 'Sample candidate protein structures without a target-specific conditioning input.',
    'Create Library': 'Organize compounds into a molecular library for subsequent analysis.',
    'Deepcodon': 'A codon-related workflow listed in the catalog; its detailed capabilities are not yet documented.',
    'Formulation Search': 'Search formulation information; this catalog entry is not currently available for execution.',
    'Fragments': 'A molecular-fragment catalog entry; its detailed workflow is not yet documented.',
    'Interactive Builder': 'An interactive molecular-building catalog entry; its detailed workflow is not yet documented.',
    'QM-MM Single-Point Energy': 'Estimate energy using combined quantum and molecular mechanics; this catalog entry is not currently available for execution.',
    'Toxicophore Screening': 'Screen molecules for structural features associated with toxicity risk.',
}


def descriptions():
    from sci_cli.science_catalog_view import registry_path
    data = json.loads(registry_path().read_text(encoding='utf-8-sig'))
    modules = {m['id']: m for m in data['modules']}
    tools = data['tools']
    tools = list(tools.values()) if isinstance(tools, dict) else tools
    result = {}
    for tool in [*tools, *data.get('unavailable_entries', [])]:
        name = tool['display_name']
        text = (tool.get('public_documentation', {}).get('public_description') or tool.get('description') or '').strip()
        text = _LABEL_DEFINITIONS.get(name, text)
        if not text or text == name:
            text = 'This tool is listed in the catalog, but a detailed definition is not yet available.'
        # Use the first complete sentence, rather than clipping words mid-definition.
        text = re.split(r'(?<=[.!?])\s+', text)[0].replace('**', '').replace('`', '')
        module = modules.get(tool.get('module_id'), {}).get('title', 'Unassigned')
        result[(module, name)] = text
    return result
