from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Job:
    id: str
    cmd: List[str]
    start_time: float = field(default_factory=time.time)
    process: Optional[subprocess.Popen] = None
    stdout_path: Path = field(
        default_factory=lambda: Path(".logs") / f"job-{int(time.time()*1000)}.out"
    )
    stderr_path: Path = field(
        default_factory=lambda: Path(".logs") / f"job-{int(time.time()*1000)}.err"
    )
    returncode: Optional[int] = None


class JobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        Path(".logs").mkdir(parents=True, exist_ok=True)
        Path(".checkpoints").mkdir(parents=True, exist_ok=True)

    def _run_job(self, job: Job):
        stdout_f = job.stdout_path.open("ab")
        stderr_f = job.stderr_path.open("ab")
        try:
            proc = subprocess.Popen(
                job.cmd, stdout=stdout_f, stderr=stderr_f, close_fds=True
            )
            job.process = proc
            proc.wait()
            job.returncode = proc.returncode
        finally:
            stdout_f.close()
            stderr_f.close()

    def start(self, cmd: List[str]) -> Job:
        job_id = f"job-{int(time.time()*1000)}"
        job = Job(id=job_id, cmd=cmd)
        with self._lock:
            self._jobs[job_id] = job
        t = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        t.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> List[Dict[str, object]]:
        with self._lock:
            data = []
            for job in self._jobs.values():
                pid = job.process.pid if job.process else None
                status = "running"
                if job.returncode is not None:
                    status = "succeeded" if job.returncode == 0 else "failed"
                data.append(
                    {
                        "job_id": job.id,
                        "status": status,
                        "pid": pid,
                        "returncode": job.returncode,
                        "started_at": job.start_time,
                        "stdout": str(job.stdout_path),
                        "stderr": str(job.stderr_path),
                        "cmd": job.cmd,
                    }
                )
            # newest first
            data.sort(key=lambda x: x["started_at"], reverse=True)
            return data

    def logs(self, job_id: str) -> Dict[str, str]:
        job = self.get(job_id)
        if not job:
            raise KeyError(job_id)
        stdout = (
            job.stdout_path.read_text(errors="ignore")
            if job.stdout_path.exists()
            else ""
        )
        stderr = (
            job.stderr_path.read_text(errors="ignore")
            if job.stderr_path.exists()
            else ""
        )
        return {"stdout": stdout, "stderr": stderr}


# Singleton manager
JOB_MANAGER = JobManager()
