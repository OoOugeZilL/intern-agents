"""Provides command-line entry points for serving the backend and preparing BIRD data."""

from pathlib import Path
import importlib.util

import typer
import uvicorn

from askdata.core.errors import AppError
from askdata.bird.birdprep import BirdPrep
from askdata.app.queryservice import QueryService
from askdata.app.sessionstore import SessionStore
from askdata.chat_session import ChatSession
from askdata.core.config import LoadSettings

cli = typer.Typer()


@cli.command("prepare-bird")
def PrepareBird(rawDir: Path = typer.Option(Path("data/bird/raw"), "--rawdir"), outDir: Path = typer.Option(Path("data/bird/processed"), "--outdir"), demoDir: Path = typer.Option(Path("data/bird/demo"), "--demodir"), force: bool = typer.Option(False, "--force"), split: str = typer.Option("mini_dev_sqlite", "--split", help="BIRD dataset split: mini_dev_sqlite or dev")):
    """Prepares local BIRD SQLite files into processed backend files."""
    try:
        result = BirdPrep().Prepare(rawDir, outDir, demoDir, force=force, split=split)
        typer.echo(result.model_dump_json())
    except AppError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error


@cli.command("serve")
def Serve(host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8000, "--port"), reload: bool = typer.Option(False, "--reload")):
    """Runs the FastAPI backend server."""
    uvicorn.run("askdata.api.main:app", host=host, port=port, reload=reload)


@cli.command("smoke")
def Smoke():
    """Runs the lightweight backend smoke test."""
    try:
        smokePath = Path("scripts/smoketest.py")
        spec = importlib.util.spec_from_file_location("askdataSmokeTest", smokePath)
        smokeModule = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smokeModule)
        smokeModule.SmokeTest()
    except AppError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error


@cli.command("gen-instructions")
def GenInstructions(processedDir: Path = typer.Option(Path("data/bird/processed"), "--processed"), outDir: Path = typer.Option(Path("data/bird/instructions"), "--out")):
    """Generates per-database instructions.md files from processed schema. Edit the files to add business term mappings."""
    genPath = Path("scripts/geninstructions.py")
    spec = importlib.util.spec_from_file_location("genInstructions", genPath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    count = mod.Generate(str(processedDir), str(outDir))
    typer.echo(f"Generated {count} instructions files in {outDir}/")


@cli.command("chat")
def Chat(database: str = typer.Option(None, "--database", "-d", help="Force a specific database instead of auto-detection")):
    """Starts an interactive chat session. Ask questions in plain English."""
    settings = LoadSettings()
    store = SessionStore()
    service = QueryService(sessionStore=store, settings=settings)
    session = ChatSession(queryService=service, databaseId=database)
    session.Start()


def Main():
    """Runs the Typer command-line application."""
    cli()
