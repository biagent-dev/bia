import gzip
import os
import shutil
import tarfile
import tempfile
from urllib.parse import quote

import GEOparse
import h5py
import requests
import scipy
from bs4 import BeautifulSoup
from GEOparse.GEOTypes import GSE, GSM
from scispacy.candidate_generation import CandidateGenerator

from biagent.types import FileType
from biagent.utils.logger import biagent_logger as logger

GEO_PATH = tempfile.gettempdir()
GEO_BASE_URL = "https://www.ncbi.nlm.nih.gov"
BASE_HEADER = {
    "authority": "www.ncbi.nlm.nih.gov",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,hi;q=0.7,zh-TW;q=0.6,fr;q=0.5",
    "cache-control": "no-cache",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.ncbi.nlm.nih.gov",
    "pragma": "no-cache",
    "referer": "https://www.ncbi.nlm.nih.gov/gds",
    "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
}


def _request_url(url, data, headers) -> BeautifulSoup:
    response = requests.post(url=url, headers=headers, data=data, timeout=20)
    response.encoding = "utf-8"
    html = response.text
    bs = BeautifulSoup(html, "lxml")
    return bs


def _format_key(string):
    return string.lower().replace(" ", "_")


def search_geo_records(keyword: str, max_records: int = 10) -> list[dict]:
    """
    Search for GEO records based on the given keyword
    :param keyword: the keyword to search for
    :param max_records: the maximum number of records to return
    :return: a list of dictionaries containing the search results
    """
    result = []

    try:
        payload = f"term={quote(keyword)}&EntrezSystem2.PEntrez.Gds.Gds_ResultsPanel.Gds_DisplayBar.PageSize={max_records}"
        bs = _request_url(url=GEO_BASE_URL + "/gds", data=payload, headers=BASE_HEADER)
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to request: {e}")
        return result

    rprts = bs.find_all("div", attrs={"class": "rprt"})
    if not rprts:
        logger.info("Failed to find records")
        return result

    for rprt in rprts:
        title = rprt.find("p", attrs={"class": "title"}).text.strip()
        article_info = {"title": title}

        supp = rprt.find("div", attrs={"class": "supp"})
        if supp:
            try:
                summary = (
                    supp.text.replace("more...", "")
                    .replace("(Submitter supplied) ", "")
                    .split("Organism")[0]
                    .strip()
                )
                article_info["summary"] = summary
            except Exception as summary_e:
                logger.error(f"Failed to get summary: {summary_e}")

            details = supp.find_all("dl", attrs={"class": "details"})
            if details:
                for detail in details:
                    try:
                        dt = detail.find("dt").text.replace(":", "").strip()
                        dd = detail.find("dd").text.strip()
                        article_info[_format_key(dt)] = dd
                    except Exception as detail_e:
                        logger.error(f"Failed to get detail: {detail_e}")
                        continue

        aux = rprt.find("div", attrs={"class": "aux"})
        if aux:
            rprtids = aux.find_all("dl", attrs={"class": "rprtid"})
            if rprtids:
                for rprtid in rprtids:
                    try:
                        dt = rprtid.find("dt").text.replace(":", "").strip()
                        dd = rprtid.find("dd").text.strip()
                        article_info[_format_key(dt)] = dd
                    except Exception as rprtid_e:
                        logger.error(f"Failed to get rprtid: {rprtid_e}")
                        continue
            try:
                links = aux.find("p", attrs={"class": "links"})
                a_tags = links.find_all("a")
                if a_tags:
                    for a_tag in a_tags:
                        article_info[_format_key(a_tag.text)] = (
                            GEO_BASE_URL + a_tag.attrs.get("href")
                        )
            except Exception as links_e:
                logger.error(f"Failed to get links: {links_e}")
        article_info["url"] = (
            f"{GEO_BASE_URL}/geo/query/acc.cgi?acc={article_info['accession']}"
        )

        result.append(article_info)

    return result


class UMLSMapper:
    def __init__(self, threshold):
        self.candidate_generator = CandidateGenerator(name="umls")
        self.kb = self.candidate_generator.kb
        self.threshold = threshold

    def __call__(self, disease):
        if disease is None:
            return None
        predicted = []
        batch_candidates = self.candidate_generator([disease], 30)
        for cand in batch_candidates[0]:
            score = max(cand.similarities)
            if (
                score < self.threshold
                or self.kb.cui_to_entity[cand.concept_id].definition is None
            ):
                continue
            if score > self.threshold:
                predicted.append((cand.concept_id, score))

        if len(predicted) > 0:
            sorted_predicted = sorted(predicted, reverse=True, key=lambda x: x[1])[0]
            entity = self.kb.cui_to_entity[sorted_predicted[0]]
            name = f"{entity.canonical_name} [{entity.concept_id}]"
            return name
        else:
            return disease


def get_geo(geo_id, return_gse=False) -> GSM | tuple[GSM, GSE]:
    if return_gse:
        gsm = GEOparse.get_GEO(geo=geo_id, destdir=GEO_PATH, silent=True)

        gse = gsm.get_metadata_attribute("series_id")
        if isinstance(gse, list):
            logger.info(
                f"Multiple GSE IDs found for {geo_id}: {gse}, using the first one"
            )
            gse = gse[0]
        gse = GEOparse.get_GEO(geo=gse, destdir=GEO_PATH, silent=True)
        return gsm, gse
    return GEOparse.get_GEO(geo=geo_id, destdir=GEO_PATH, silent=True)


def process_lines(file_handle):
    """
    Process the file lines, truncating if necessary.
    """
    lines = []
    counts = 0
    while True:
        line = file_handle.readline()
        if not line:
            break  # End of file reached
        counts += 1
        if counts > 10:
            continue
        if len(line) > 100:
            line = line[:100] + f"... [{len(line) - 100} characters truncated]"
        lines.append(line)
    lines.append("...")
    lines.append(f"[Total {counts} lines]")
    return "\n".join(lines)


def process_h5_file(file_handle):
    """
    Generate a summary of the HDF5 file's structure and dataset details.
    """
    summary = []

    def summarize(name, obj):
        if isinstance(obj, h5py.Dataset):
            summary.append(f"Dataset: {name}, Shape: {obj.shape}, Type: {obj.dtype}")
            # Add more details or data samples here as needed
        elif isinstance(obj, h5py.Group):
            summary.append(f"Group: {name}")

    file_handle.visititems(summarize)
    summary = summary if summary else ["No groups or datasets found in the HDF5 file."]
    return "\n".join(summary)


def extract_mat_summary(mat_contents):
    """
    Extract summary from MATLAB file contents.
    """
    summary = []
    for var_name, data in mat_contents.items():
        if not var_name.startswith("__"):
            summary.append(
                f"Variable: {var_name}, Type: {type(data).__name__}, Shape: {data.shape if hasattr(data, 'shape') else 'N/A'}"
            )

    summary = summary if summary else ["No variables found in the MAT file."]
    return "\n".join(summary)


def process_soft_files(
    soft_file_path: str, max_gsms_per_gse: int = None
) -> list[tuple[GSM, GSE]]:
    try:
        geo = GEOparse.get_GEO(filepath=soft_file_path, silent=True)
    except EOFError as e:
        logger.error(f"Error parsing {soft_file_path}: {e}")
        return []

    if isinstance(geo, GSE):
        gsms = list(geo.gsms.values())
        if max_gsms_per_gse:
            gsms = gsms[:max_gsms_per_gse]
        return [(gsm, geo) for gsm in gsms]
    elif isinstance(geo, GSM):
        return [get_geo(geo.get_accession(), return_gse=True)]


def _peek_file_content(filename: str, directory: str):
    """
    This function returns the first 10 lines of the file.
    Lines will be truncated if too long (> 100 characters, total character number info will be added).
    The file might be a compressed file (e.g., .zip, .gz).
    """
    # Construct the full file path
    filepath = os.path.join(directory, filename)
    logger.info("reading file: {}", filepath)

    chosen_open_func = open
    if filename.endswith(".gz"):
        with gzip.open(filepath, "rb") as f:
            new_filepath = "/tmp/" + filename.removesuffix(".gz")
            with open(new_filepath, "wb") as f_out:
                shutil.copyfileobj(f, f_out)
            filepath = new_filepath
    filename = filename.removesuffix(".gz")

    if filename.lower().endswith(".h5"):
        with h5py.File(filepath, "r") as f:
            return process_h5_file(f)
    # elif any([filename.lower().endswith(ext) for ext in not_avaliable_extensions]):
    #     return NOT_AVAILABLE
    elif filename.lower().endswith(".mat"):
        mat_contents = scipy.io.loadmat(filepath)
        return extract_mat_summary(mat_contents)
    elif (
        filename.lower().endswith(".rds")
        or filename.lower().endswith(".rdata")
        or filename.lower().endswith(".rdat")
    ):
        raise NotImplementedError()
    else:
        with chosen_open_func(filepath, "rt") as f:
            return process_lines(f)


def get_supp_data(gsm_id: str) -> dict:
    res = {"files": [], "dir": None, "content": []}
    gsm = get_geo(gsm_id)
    logger.info("{} will download", gsm_id)
    gsm.download_supplementary_files(directory=GEO_PATH, download_sra=False)

    for f in os.listdir(GEO_PATH):
        if os.path.isdir(os.path.join(GEO_PATH, f)) and (gsm_id in f):
            res["files"] = os.listdir(os.path.join(GEO_PATH, f))
            res["dir"] = os.path.join(GEO_PATH, f)
            new_files = []
            for gsm_file in res["files"]:
                if ".tar" in gsm_file:
                    file = tarfile.open(os.path.join(res["dir"], gsm_file))
                    file.extractall(res["dir"])
                    file.close()

                    for cur_dir, _, cur_files in os.walk(res["dir"]):
                        if len(cur_files) > 0:
                            for cur_file in cur_files:
                                if cur_file == gsm_file:
                                    continue
                                shutil.move(
                                    os.path.join(cur_dir, cur_file),
                                    os.path.join(res["dir"], cur_file),
                                )
                                new_files.append(cur_file)
                    new_files = list(set(new_files))  # remove duplicates
                elif os.path.isfile(os.path.join(res["dir"], gsm_file)):
                    new_files.append(gsm_file)

            res["files"] = new_files
            for gsm_file in res["files"]:
                res["content"].append(_peek_file_content(gsm_file, res["dir"]))
            break
    return res


def check_file_type(file_content: dict) -> FileType:
    file_type = FileType.UNKNOWN
    for f in file_content["files"]:
        f = f.lower()
        if "mtx" in f:
            file_type = FileType.MTX
        if "csv" in f or "txt" in f or "tsv" in f:
            file_type = FileType.TABLE
        if "rdata" in f:
            file_type = FileType.RDATA
        if ".h5." in f:
            file_type = FileType.H5
        if ".h5ad." in f:
            file_type = FileType.H5AD
    return file_type
