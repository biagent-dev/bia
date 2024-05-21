from biagent.types.pydantic_models import MetaFieldList

META_FIELD_DEFINITIONS = [
    {
        "name": "sample storage",
        "type": "str",
        "description": "fresh, frozen, Formalin-fixed, Paraffin-embedded specimen, etc, or unknown",
    },
    {
        "name": "library preparation platform",
        "type": "str",
        "description": "RNA-seq library preparation platform, for exsample 10x Chromium (v2), 10x Chromium (v3), Smart-seq2, etc",
    },
    {
        "name": "library kit",
        "type": "str",
        "description": "RNA extraction kit, for exsample PicoPure RNA Isolation kit, GeneChip 3' IVT Express Kit, etc",
    },
    {
        "name": "software for read quality control",
        "type": "str",
        "description": "e.g., cutadapt, etc",
    },
    {
        "name": "software for read alignment",
        "type": "str",
        "description": "e.g., STAR, HISAT2, etc",
    },
    {
        "name": "software for read quantification",
        "type": "str",
        "description": "e.g., RSEM, StringTie, etc ",
    },
    {
        "name": "expression calculation in the supplementary files",
        "type": "str",
        "description": "read count/CPM/FPKM/TMP, whether log transformed, use supplementary file names for more information",
    },
    {
        "name": "reference genome",
        "type": "str",
        "description": "e.g., hg19, hg38, GRCh37, GRCh38, etc ",
    },
    {
        "name": "genome annotation file",
        "type": "str",
        "description": "e.g., Homo_sapiens.GRCh38.79.gtf, GRCm38.p3 gtf, etc",
    },
    {
        "name": "bulk or single-cell or single-nucleus",
        "type": "str",
        "description": "bulk or single-cell or single-nucleus sample",
    },
    {
        "name": "condition",
        "type": "str",
        "description": "healthy, cancer (cancer type), inflammation (Inflammatory disease name), infection (origin of infection), etc. There can be multiple conditions",
        "map_to_umls": True,
    },
    {
        "name": "organ/tissue",
        "type": "str",
        "description": "origin of organ/tissue",
        "map_to_umls": True,
    },
    {
        "name": "cell line",
        "type": "str",
        "description": "If it is a cell line sample, provide the cell line name",
    },
    {"name": "gender", "type": "str", "description": ""},
    {"name": "age", "type": "str", "description": ""},
    {"name": "alcohol use", "type": "str", "description": "drinking history"},
    {"name": "tobacco use", "type": "str", "description": "smoking history"},
    {
        "name": "tumor site",
        "type": "str",
        "description": "If it is a cancer sample, what site is the sample from, for example primary, metastasis, relapse, tumor adjacent, etc",
    },
    {
        "name": "stage/state",
        "type": "str",
        "description": "disease stage such as TNM cancer stage, development stage such as gestational age",
    },
    {
        "name": "sampling site",
        "type": "str",
        "description": "such as vaginal fornix, etc",
        "map_to_umls": True,
    },
    {
        "name": "treatment",
        "type": "str",
        "description": "treatment of diseases such as radiation therapy or drugs, if any drug uses, provide drug names, there can be multiple treatments",
        "map_to_umls": True,
    },
    {
        "name": "survival time",
        "type": "str",
        "description": "overall survival, disease free survival, progression-free survival. If multiple kinds of survival time available, provide all",
    },
    {
        "name": "length of sequencing reads",
        "type": "str",
        "description": "length of sequencing reads such as 100bp",
    },
    {
        "name": "pair-end",
        "type": "str",
        "description": "single-end or pair-end sequencing",
    },
    {
        "name": "title",
        "type": "str",
        "description": "sample title",
        "ref": ["Sample_title"],
        "copy_from_ref": True,
    },
    {
        "name": "type",
        "type": "str",
        "description": "sample type",
        "ref": ["Sample_type"],
        "copy_from_ref": True,
    },
    {
        "name": "series_id",
        "type": "str",
        "description": "series id",
        "ref": ["Sample_series_id"],
        "copy_from_ref": True,
    },
    {
        "name": "pubmed_id",
        "type": "str",
        "description": "pubmed_id",
        "ref": ["Series_pubmed_id"],
        "copy_from_ref": True,
    },
    {
        "name": "platform_id",
        "type": "str",
        "description": "platform_id",
        "ref": ["Sample_platform_id"],
        "copy_from_ref": True,
    },
    {
        "name": "relation",
        "type": "str",
        "description": "relation",
        "ref": ["Sample_relation"],
        "copy_from_ref": True,
    },
]

DEFAULT_META_FIELD_GROUP = MetaFieldList.model_validate(META_FIELD_DEFINITIONS)
