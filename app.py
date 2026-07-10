"""
QuPepFold FastAPI Service

Production API wrapper around the QuPepFold quantum peptide folding engine.

Designed for:
- qFold-MCP
- Claude Science agents
- Kubernetes deployments
- Docker environments

"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


# QuPepFold imports
#
# The exact import depends on the installed package version.
# Newer versions expose fold(), older versions expose
# protein_vqe_objective().
#
from qupepfold import fold


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

APP_DIR = Path("/app")
OUTPUT_DIR = APP_DIR / "output"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

logger = logging.getLogger("qfold-service")


executor = ThreadPoolExecutor(
    max_workers=int(
        os.getenv(
            "QFOLD_WORKERS",
            "2"
        )
    )
)


app = FastAPI(
    title="qFold QuPepFold Service",
    version="1.0.0",
    description=
    """
    Quantum peptide folding microservice powered by QuPepFold CVaR-VQE.
    """
)


# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------

VALID_AMINO_ACIDS = set(
    "ACDEFGHIKLMNPQRSTVWY"
)


class FoldRequest(BaseModel):

    sequence: str = Field(
        ...,
        min_length=2,
        max_length=128,
        description="Amino acid sequence"
    )

    tries: int = Field(
        default=5,
        ge=1,
        le=100
    )

    shots: int = Field(
        default=500,
        ge=10,
        le=100000
    )

    cvar_alpha: float = Field(
        default=0.1,
        gt=0,
        le=1
    )


    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, value: str):

        seq = value.upper()

        invalid = set(seq) - VALID_AMINO_ACIDS

        if invalid:
            raise ValueError(
                f"Invalid amino acids: {invalid}"
            )

        return seq



class FoldResponse(BaseModel):

    job_id: str

    sequence: str

    status: str

    output_directory: str

    artifacts: dict

    optimized_energy: float | None = None



# ---------------------------------------------------------
# Internal Worker
# ---------------------------------------------------------


def run_qupepfold_job(
    request: FoldRequest,
    job_dir: Path
):

    logger.info(
        "Starting QuPepFold job %s",
        job_dir.name
    )


    result = fold(
        sequence=request.sequence,
        tries=request.tries,
        shots=request.shots,
        cvar_alpha=request.cvar_alpha,
        output_dir=str(job_dir)
    )


    summary_file = job_dir / "service_result.json"


    payload = {

        "completed":
            datetime.utcnow().isoformat(),

        "sequence":
            request.sequence,

        "result":
            str(result)

    }


    summary_file.write_text(
        json.dumps(
            payload,
            indent=2,
            default=str
        )
    )


    artifacts = {}

    for file in job_dir.rglob("*"):

        if file.is_file():

            artifacts[
                file.name
            ] = str(file)


    energy = None


    if isinstance(result, dict):

        energy = (
            result.get(
                "energy"
            )
            or
            result.get(
                "optimized_energy"
            )
        )


    return {

        "artifacts":
            artifacts,

        "energy":
            energy
    }



# ---------------------------------------------------------
# API
# ---------------------------------------------------------


@app.get(
    "/health"
)
async def health():

    return {

        "status":
            "healthy",

        "service":
            "qFold QuPepFold",

        "version":
            app.version

    }



@app.post(
    "/fold",
    response_model=FoldResponse
)
async def fold_peptide(
    request: FoldRequest
):

    job_id = str(
        uuid.uuid4()
    )


    job_dir = (
        OUTPUT_DIR /
        "jobs" /
        job_id
    )


    job_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    loop = asyncio.get_running_loop()


    try:

        result = await loop.run_in_executor(
            executor,
            run_qupepfold_job,
            request,
            job_dir
        )


    except Exception as exc:

        logger.exception(
            "Fold failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


    return FoldResponse(

        job_id=job_id,

        sequence=request.sequence,

        status="completed",

        output_directory=str(
            job_dir
        ),

        artifacts=result["artifacts"],

        optimized_energy=result["energy"]

    )
