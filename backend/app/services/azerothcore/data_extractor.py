"""
Client data extraction service for AzerothCore.

Provides two methods for obtaining required client data:
1. Download pre-extracted data from wowgaming/client-data releases (recommended)
2. Extract from a local WoW 3.3.5a client using extraction tools

Data types required:
- DBC files (database client data)
- Maps (map tile data)
- VMaps (virtual maps for collision/LOS)
- MMaps (movement maps for pathfinding)
"""
from __future__ import annotations

import asyncio
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Optional

# Default URL for pre-extracted data from wowgaming/client-data
# This is the official source for AzerothCore client data
DATA_URL = "https://github.com/wowgaming/client-data/releases/download/v19/data.zip"
DATA_VERSION = "v19"

# State tracking
_extraction_state: dict = {
    "in_progress": False,
    "current_step": None,
    "progress_percent": 0,
    "started_at": None,
    "error": None,
    "process": None,  # Store the running process for cancellation
}


def get_extraction_status() -> dict:
    """Get current extraction status and data presence."""
    from app.services.panel_settings import get_settings_dict
    import asyncio
    
    # Get data path from settings
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, but this is a sync function
            # Use default path
            data_path = Path("/opt/azerothcore/build/data")
        else:
            settings = loop.run_until_complete(get_settings_dict())
            data_path = Path(settings.get("AC_DATA_PATH", "/opt/azerothcore/build/data"))
    except:
        data_path = Path("/opt/azerothcore/build/data")
    
    # Check which data directories exist and have content
    dbc_path = data_path / "dbc"
    maps_path = data_path / "maps"
    vmaps_path = data_path / "vmaps"
    mmaps_path = data_path / "mmaps"
    
    def has_files(directory: Path) -> bool:
        if not directory.exists():
            return False
        return any(directory.iterdir()) if directory.is_dir() else False
    
    return {
        **_extraction_state,
        "data_path": str(data_path),
        "has_dbc": has_files(dbc_path),
        "has_maps": has_files(maps_path),
        "has_vmaps": has_files(vmaps_path),
        "has_mmaps": has_files(mmaps_path),
        "data_present": (
            has_files(dbc_path) and 
            has_files(maps_path) and 
            has_files(vmaps_path)
        ),
    }


async def _run_command(
    cmd: str,
    cwd: str | None = None,
    extra_env: dict | None = None,
    rc_out: list | None = None,
) -> AsyncIterator[str]:
    """
    Stream a shell command's combined stdout+stderr line-by-line.
    Similar to the installer's _run function.
    rc_out receives [returncode] after the process finishes.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    
    proc = await asyncio.create_subprocess_shell(
        f"stdbuf -oL -eL {cmd}",
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    
    _extraction_state["process"] = proc
    
    assert proc.stdout
    buf = ""
    while True:
        chunk = await proc.stdout.read(512)
        if not chunk:
            break
        buf += chunk.decode("utf-8", errors="replace")
        lines = buf.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        buf = lines.pop()
        for line in lines:
            s = line.rstrip()
            if s:
                yield s
        await asyncio.sleep(0)
    
    if buf.strip():
        yield buf.strip()
    
    await proc.wait()
    _extraction_state["process"] = None
    
    if rc_out is not None:
        rc_out.append(proc.returncode)
    
    if proc.returncode != 0:
        yield f"[exit {proc.returncode}]"


async def download_preextracted_data(
    data_path: str,
    data_url: str = DATA_URL,
) -> AsyncIterator[str]:
    """
    Download and extract pre-generated client data from wowgaming/client-data releases.
    
    This is the recommended method - fastest and easiest.
    Downloads data.zip (~1.5GB) and extracts to data_path.
    """
    global _extraction_state
    
    _extraction_state = {
        "in_progress": True,
        "current_step": "download",
        "progress_percent": 0,
        "started_at": datetime.utcnow().isoformat(),
        "error": None,
        "process": None,
    }
    
    data_dir = Path(data_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    zip_file = data_dir / "data.zip"
    
    try:
        # Check disk space (need at least 6GB)
        yield "[step:check] Checking disk space..."
        stat = shutil.disk_usage(data_dir)
        free_gb = stat.free / (1024**3)
        if free_gb < 6:
            yield f"[error] Insufficient disk space: {free_gb:.1f}GB free, need at least 6GB"
            _extraction_state["in_progress"] = False
            _extraction_state["error"] = f"Insufficient disk space: {free_gb:.1f}GB"
            return
        
        yield f"[check] Disk space OK: {free_gb:.1f}GB free"
        
        # Download data.zip
        yield f"[step:download] Downloading client data from {data_url}..."
        yield "[download] This may take 2-10 minutes depending on your connection..."
        
        # Check which download tool is available
        has_wget = shutil.which("wget") is not None
        has_curl = shutil.which("curl") is not None
        
        if not has_wget and not has_curl:
            yield "[error] Neither wget nor curl is installed. Please install one of them."
            _extraction_state["in_progress"] = False
            _extraction_state["error"] = "No download tool available"
            return
        
        if has_wget:
            # Use wget with progress bar
            download_cmd = (
                f"wget -q --show-progress --progress=bar:force "
                f"-O {zip_file} '{data_url}'"
            )
        else:
            # Use curl as fallback with progress bar
            download_cmd = (
                f"curl -L --progress-bar -o {zip_file} '{data_url}'"
            )
        
        returncode = 0
        async for line in _run_command(download_cmd, cwd=str(data_dir)):
            # Parse download progress output
            if "%" in line:
                try:
                    # Extract percentage from wget/curl output
                    parts = line.split()
                    for part in parts:
                        if "%" in part:
                            pct = int(part.replace("%", ""))
                            _extraction_state["progress_percent"] = pct
                            yield f"[download] {line}"
                            break
                except:
                    yield f"[download] {line}"
            else:
                yield f"[download] {line}"
        
        # Check if download succeeded
        if not zip_file.exists():
            yield "[error] Download failed - file not created"
            _extraction_state["in_progress"] = False
            _extraction_state["error"] = "Download failed"
            return
        
        file_size_mb = zip_file.stat().st_size / (1024**2)
        yield f"[download] Download complete: {file_size_mb:.1f} MB"
        
        # Check if unzip is available
        if shutil.which("unzip") is None:
            yield "[error] unzip is not installed. Please install it (apt install unzip)."
            _extraction_state["in_progress"] = False
            _extraction_state["error"] = "unzip not available"
            return
        
        # Extract zip file
        _extraction_state["current_step"] = "extract"
        _extraction_state["progress_percent"] = 0
        yield "[step:extract] Extracting data.zip..."
        yield "[extract] This may take 1-2 minutes..."
        
        extract_cmd = f"unzip -o {zip_file} -d {data_dir}"
        
        async for line in _run_command(extract_cmd, cwd=str(data_dir)):
            yield f"[extract] {line}"
        
        # Verify extraction
        yield "[step:verify] Verifying extracted data..."
        
        dbc_dir = data_dir / "dbc"
        maps_dir = data_dir / "maps"
        vmaps_dir = data_dir / "vmaps"
        mmaps_dir = data_dir / "mmaps"
        
        def check_dir(name: str, path: Path) -> tuple[bool, str]:
            if path.exists() and any(path.iterdir()):
                file_count = sum(1 for _ in path.rglob("*") if _.is_file())
                return True, f"[verify] {name}: {file_count} files"
            else:
                return False, f"[verify] {name}: NOT FOUND"
        
        has_dbc, msg = check_dir("DBC", dbc_dir)
        yield msg
        
        has_maps, msg = check_dir("Maps", maps_dir)
        yield msg
        
        has_vmaps, msg = check_dir("VMaps", vmaps_dir)
        yield msg
        
        has_mmaps, msg = check_dir("MMaps", mmaps_dir)
        yield msg
        
        # Clean up zip file
        yield "[cleanup] Removing downloaded archive..."
        zip_file.unlink()
        
        _extraction_state["in_progress"] = False
        _extraction_state["current_step"] = None
        _extraction_state["progress_percent"] = 100
        
        if has_dbc and has_maps and has_vmaps:
            yield "[done] Client data download complete! You can now start the servers."
        else:
            yield "[warning] Some data may be missing. Check the extraction logs."
        
    except Exception as e:
        _extraction_state["in_progress"] = False
        _extraction_state["error"] = str(e)
        yield f"[error] {str(e)}"
        
        # Clean up partial files
        if zip_file.exists():
            zip_file.unlink()


async def extract_from_client(
    client_path: str,
    data_path: str,
    binary_path: str,
    options: dict,
) -> AsyncIterator[str]:
    """
    Extract client data from a local WoW 3.3.5a client.
    
    Options:
        extract_dbc: bool = True
        extract_maps: bool = True
        extract_vmaps: bool = True
        generate_mmaps: bool = True
    """
    global _extraction_state
    
    _extraction_state = {
        "in_progress": True,
        "current_step": "validate",
        "progress_percent": 0,
        "started_at": datetime.utcnow().isoformat(),
        "error": None,
        "process": None,
    }
    
    client_dir = Path(client_path)
    data_dir = Path(data_path)
    binary_dir = Path(binary_path)
    
    # Validate client path
    yield "[step:validate] Validating client path..."
    
    # First check if the path exists at all
    if not client_dir.exists():
        yield f"[error] Client path does not exist: {client_path}"
        _extraction_state["in_progress"] = False
        _extraction_state["error"] = f"Client path does not exist: {client_path}"
        return
    
    if not client_dir.is_dir():
        yield f"[error] Client path is not a directory: {client_path}"
        _extraction_state["in_progress"] = False
        _extraction_state["error"] = f"Client path is not a directory: {client_path}"
        return
    
    # Check for valid WoW client structure
    client_valid = False
    if (client_dir / "Wow.exe").exists():
        yield "[validate] Found Wow.exe - Windows client detected"
        client_valid = True
    elif (client_dir / "MacOS" / "World of Warcraft").exists():
        yield "[validate] Found MacOS/World of Warcraft - Mac client detected"
        client_valid = True
    elif (client_dir / "Data").exists() and (client_dir / "Data").is_dir():
        # Check if Data directory contains MPQ files or locale directories
        data_subdir = client_dir / "Data"
        has_mpq = any(data_subdir.glob("*.mpq"))
        has_locale = (data_subdir / "enUS").exists() or (data_subdir / "enGB").exists()
        if has_mpq or has_locale:
            yield "[validate] Found Data directory with client data - valid client path"
            client_valid = True
        else:
            yield "[validate] Found Data directory - attempting extraction"
            client_valid = True
    elif any(client_dir.glob("*.mpq")):
        # Check for MPQ files directly in the provided path
        yield "[validate] Found MPQ files - client data path detected"
        client_valid = True
    elif (client_dir / "enUS").exists() or (client_dir / "enGB").exists():
        # Check for locale directories (user might point directly to Data folder)
        yield "[validate] Found locale directory - client data path detected"
        client_valid = True
    else:
        # List what we found in the directory for debugging
        try:
            contents = list(client_dir.iterdir())[:10]  # First 10 items
            content_names = [f.name for f in contents]
            yield f"[validate] Directory contents: {', '.join(content_names[:5])}..."
        except Exception as e:
            yield f"[validate] Could not list directory contents: {e}"
        
        # Allow proceeding anyway - the extraction tools might still work
        yield "[validate] No standard WoW client structure detected, but proceeding anyway"
        client_valid = True
    
    if not client_valid:
        yield "[error] Invalid client path. Expected Wow.exe, Data directory, or MPQ files."
        _extraction_state["in_progress"] = False
        _extraction_state["error"] = "Invalid client path"
        return
    
    # Check extraction tools
    yield "[step:tools] Checking extraction tools..."
    
    # List of possible tool names and locations
    # Note: AzerothCore uses underscore naming (map_extractor) while some docs use no underscore
    tool_names = {
        "mapextractor": ["map_extractor", "mapextractor", "map_extractor.exe", "mapextractor.exe"],
        "vmap4extractor": ["vmap4_extractor", "vmap4extractor", "vmap4_extractor.exe", "vmap4extractor.exe"],
        "vmap4assembler": ["vmap4_assembler", "vmap4assembler", "vmap4_assembler.exe", "vmap4assembler.exe"],
        "mmaps_generator": ["mmaps_generator", "mmaps_generator.exe", "MoveMapGen", "MoveMapGen.exe"],
    }
    
    def find_tool(names: list[str]) -> Path | None:
        """Search for a tool in binary_dir and common subdirectories."""
        # Search in multiple possible locations
        # After cmake install, tools should be in {build_path}/bin/
        # But they might also be in the build directory itself before install
        search_dirs = [
            binary_dir,  # AC_BINARY_PATH (typically /opt/azerothcore/build/bin)
            data_dir.parent / "bin",  # build/bin (same as above usually)
            data_dir.parent,  # AC_BUILD_PATH (build root - tools might be here before install)
            # Also check build type subdirectories (cmake sometimes puts them there)
            data_dir.parent / "bin" / "RelWithDebInfo",
            data_dir.parent / "bin" / "Debug",
            data_dir.parent / "bin" / "Release",
        ]
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for name in names:
                tool_path = search_dir / name
                if tool_path.exists():
                    return tool_path
        return None
    
    # Find tools
    mapextractor = find_tool(tool_names["mapextractor"])
    vmap4extractor = find_tool(tool_names["vmap4extractor"])
    vmap4assembler = find_tool(tool_names["vmap4assembler"])
    mmaps_generator = find_tool(tool_names["mmaps_generator"])
    
    tools_ok = True
    if not mapextractor:
        yield f"[error] mapextractor not found in {binary_dir}"
        tools_ok = False
    else:
        yield f"[tools] Found mapextractor at {mapextractor}"
    
    if options.get("extract_vmaps", True):
        if not vmap4extractor:
            yield f"[error] vmap4extractor not found in {binary_dir}"
            tools_ok = False
        else:
            yield f"[tools] Found vmap4extractor at {vmap4extractor}"
        if not vmap4assembler:
            yield f"[error] vmap4assembler not found in {binary_dir}"
            tools_ok = False
        else:
            yield f"[tools] Found vmap4assembler at {vmap4assembler}"
    
    if options.get("generate_mmaps", True):
        if not mmaps_generator:
            yield f"[error] mmaps_generator not found in {binary_dir}"
            tools_ok = False
        else:
            yield f"[tools] Found mmaps_generator at {mmaps_generator}"
    
    if not tools_ok:
        yield "[error] Missing extraction tools."
        yield "[error] Ensure compilation was run with -DTOOLS_BUILD=all cmake option."
        yield f"[error] Binary path configured: {binary_dir}"
        yield f"[error] Build path: {data_dir.parent}"
        # List what's in the binary and build directories for debugging
        for check_dir in [binary_dir, data_dir.parent, data_dir.parent / "bin"]:
            if check_dir.exists():
                try:
                    contents = list(check_dir.iterdir())
                    if contents:
                        yield f"[debug] Contents of {check_dir}: {[f.name for f in contents[:20]]}"
                    else:
                        yield f"[debug] Directory {check_dir} is empty"
                except Exception as e:
                    yield f"[debug] Could not list {check_dir}: {e}"
            else:
                yield f"[debug] Directory {check_dir} does not exist"
        _extraction_state["in_progress"] = False
        _extraction_state["error"] = "Missing extraction tools"
        return
    
    # Create data directories
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "dbc").mkdir(exist_ok=True)
    (data_dir / "maps").mkdir(exist_ok=True)
    (data_dir / "vmaps").mkdir(exist_ok=True)
    (data_dir / "mmaps").mkdir(exist_ok=True)
    
    total_steps = sum([
        1 if options.get("extract_dbc", True) or options.get("extract_maps", True) else 0,
        2 if options.get("extract_vmaps", True) else 0,
        1 if options.get("generate_mmaps", True) else 0,
    ])
    current_step = 0
    
    # Extract DBC and Maps (done together by mapextractor)
    if options.get("extract_dbc", True) or options.get("extract_maps", True):
        _extraction_state["current_step"] = "dbc_maps"
        current_step += 1
        _extraction_state["progress_percent"] = int((current_step / total_steps) * 100)
        
        yield f"[step:dbc_maps] Extracting DBC and Maps ({current_step}/{total_steps})..."
        yield "[dbc_maps] This may take 2-5 minutes..."
        
        # Clean up any previous extraction artifacts
        for folder in ["dbc", "maps", "Cameras"]:
            folder_path = client_dir / folder
            if folder_path.exists():
                yield f"[dbc_maps] Cleaning up previous {folder} folder..."
                shutil.rmtree(folder_path)
        
        # map_extractor runs from the client directory and extracts dbc, maps, Cameras
        # It looks for Data folder in current directory
        cmd = f"{mapextractor}"
        
        async for line in _run_command(cmd, cwd=str(client_dir)):
            yield f"[dbc_maps] {line}"
        
        # Move extracted files to data directory
        yield "[dbc_maps] Moving extracted files to data directory..."
        for folder in ["dbc", "maps", "Cameras"]:
            src = client_dir / folder
            if src.exists():
                dst = data_dir / folder
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(src), str(dst))
                yield f"[dbc_maps] Moved {folder} to {data_dir}"
        
        yield "[dbc_maps] DBC and Maps extraction complete"
    
    # Extract VMaps
    if options.get("extract_vmaps", True):
        _extraction_state["current_step"] = "vmaps_extract"
        current_step += 1
        _extraction_state["progress_percent"] = int((current_step / total_steps) * 100)
        
        yield f"[step:vmaps] Extracting VMaps ({current_step}/{total_steps})..."
        yield "[vmaps] Step 1/2: Extracting raw vmap data..."
        yield "[vmaps] Note: 'No such file' and 'Couldn't open RootWmo' warnings are normal."
        
        # Clean up any previous extraction artifacts
        buildings_dir = client_dir / "Buildings"
        if buildings_dir.exists():
            yield "[vmaps] Cleaning up previous Buildings folder..."
            shutil.rmtree(buildings_dir)
        
        vmaps_tmp = client_dir / "vmaps"
        if vmaps_tmp.exists():
            shutil.rmtree(vmaps_tmp)
        
        # vmap4_extractor needs -s (small) or -l (large) flag
        # -s is default and creates ~500MB less data
        cmd = f"{vmap4extractor} -s"
        
        async for line in _run_command(cmd, cwd=str(client_dir)):
            yield f"[vmaps] {line}"
        
        # Check if Buildings was created
        buildings_dir = client_dir / "Buildings"
        if not buildings_dir.exists():
            yield "[vmaps] Warning: Buildings folder not created, checking alternative locations..."
            # Sometimes it's created in the current working directory
            buildings_dir = Path.cwd() / "Buildings"
            if not buildings_dir.exists():
                yield "[vmaps] Error: Buildings folder not found. VMap extraction may have failed."
        
        _extraction_state["current_step"] = "vmaps_assemble"
        current_step += 1
        _extraction_state["progress_percent"] = int((current_step / total_steps) * 100)
        
        yield "[vmaps] Step 2/2: Assembling VMaps..."
        
        # vmap4_assembler takes Buildings folder and outputs to vmaps
        # Run from client directory where Buildings was created
        cmd = f"{vmap4assembler} Buildings vmaps"
        
        async for line in _run_command(cmd, cwd=str(client_dir)):
            yield f"[vmaps] {line}"
        
        # Move vmaps to data directory
        yield "[vmaps] Moving vmaps to data directory..."
        src = client_dir / "vmaps"
        if src.exists():
            dst = data_dir / "vmaps"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
            yield f"[vmaps] Moved vmaps to {data_dir}"
        else:
            yield "[vmaps] Warning: vmaps folder not found in client directory"
        
        # Clean up Buildings folder
        if buildings_dir.exists():
            shutil.rmtree(buildings_dir)
            yield "[vmaps] Cleaned up temporary Buildings folder"
        
        yield "[vmaps] VMaps extraction complete"
    
    # Generate MMaps
    if options.get("generate_mmaps", True):
        _extraction_state["current_step"] = "mmaps"
        current_step += 1
        _extraction_state["progress_percent"] = int((current_step / total_steps) * 100)
        
        yield f"[step:mmaps] Generating MMaps ({current_step}/{total_steps})..."
        yield "[mmaps] WARNING: This may take 30-60 minutes!"
        yield "[mmaps] Movement maps are optional but recommended for better pathfinding."
        
        # mmaps_generator needs both maps AND vmaps in the current directory
        # Check if vmaps exists
        vmaps_src = data_dir / "vmaps"
        if not vmaps_src.exists() or not any(vmaps_src.iterdir()):
            yield "[mmaps] Error: VMaps are required for MMaps generation."
            yield "[mmaps] Please enable and complete VMaps extraction first."
            yield "[mmaps] Skipping MMaps generation."
        else:
            # Clean up previous mmaps
            mmaps_tmp = client_dir / "mmaps"
            if mmaps_tmp.exists():
                shutil.rmtree(mmaps_tmp)
            mmaps_tmp.mkdir()
            
            # Copy maps and vmaps to client dir for mmaps_generator
            maps_src = data_dir / "maps"
            maps_tmp = client_dir / "maps"
            vmaps_tmp = client_dir / "vmaps"
            
            if maps_src.exists():
                if maps_tmp.exists():
                    shutil.rmtree(maps_tmp)
                yield "[mmaps] Copying maps to client directory..."
                shutil.copytree(maps_src, maps_tmp)
            
            if vmaps_src.exists():
                if vmaps_tmp.exists():
                    shutil.rmtree(vmaps_tmp)
                yield "[mmaps] Copying vmaps to client directory..."
                shutil.copytree(vmaps_src, vmaps_tmp)
            
            cmd = f"{mmaps_generator}"
            
            async for line in _run_command(cmd, cwd=str(client_dir)):
                yield f"[mmaps] {line}"
            
            # Move mmaps to data directory
            yield "[mmaps] Moving mmaps to data directory..."
            src = client_dir / "mmaps"
            if src.exists() and any(src.iterdir()):
                dst = data_dir / "mmaps"
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.move(str(src), str(dst))
                yield f"[mmaps] Moved mmaps to {data_dir}"
            else:
                yield "[mmaps] Warning: mmaps folder not found or empty"
            
            # Clean up temporary copies
            if maps_tmp.exists():
                shutil.rmtree(maps_tmp)
                yield "[mmaps] Cleaned up temporary maps folder"
            if vmaps_tmp.exists():
                shutil.rmtree(vmaps_tmp)
                yield "[mmaps] Cleaned up temporary vmaps folder"
        
        yield "[mmaps] MMaps generation complete"
    
    _extraction_state["in_progress"] = False
    _extraction_state["current_step"] = None
    _extraction_state["progress_percent"] = 100
    
    yield "[done] Client data extraction complete! You can now start the servers."


async def cancel_extraction() -> bool:
    """Cancel any running extraction process."""
    global _extraction_state
    
    if not _extraction_state["in_progress"]:
        return False
    
    proc = _extraction_state.get("process")
    if proc:
        try:
            proc.terminate()
            await asyncio.sleep(1)
            if proc.returncode is None:
                proc.kill()
        except:
            pass
    
    _extraction_state["in_progress"] = False
    _extraction_state["current_step"] = "cancelled"
    _extraction_state["error"] = "Cancelled by user"
    
    return True
