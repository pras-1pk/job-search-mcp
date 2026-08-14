"""Tools package for job-search-mcp."""

__all__ = ["search_jobs", "score_job", "analyse_job", "prefilter_jobs", "track_job", "extract_resume_profile"]


def __getattr__(name):
    if name in {"search_jobs"}:
        from .search import search_jobs
        return search_jobs
    if name in {"score_job", "analyse_job", "prefilter_jobs"}:
        from .scorer import analyse_job, prefilter_jobs, score_job
        return {"score_job": score_job, "analyse_job": analyse_job, "prefilter_jobs": prefilter_jobs}[name]
    if name in {"track_job"}:
        from .tracker import track_job
        return track_job
    if name in {"extract_resume_profile"}:
        from .resume_parser import extract_resume_profile
        return extract_resume_profile
    raise AttributeError(name)
