"""
Automate the FloPoCo → Vivado → Simulation verification flow.

Example:
    python automate_flow.py \
        --function 'log(x+0.0001)/log(2)' \
        --lsb-in -6 --lsb-out -6
"""

from __future__ import annotations

import argparse
import shlex
import re
import shutil
import subprocess
from pathlib import Path

PY_SCRIPTS_ROOT = Path(__file__).resolve().parent
DEFAULT_FLOPOCO_DIR = PY_SCRIPTS_ROOT.parent / "flopoco"


def run_cmd(cmd: list[str], cwd: Path | None = None) -> None:
    workdir = cwd or PY_SCRIPTS_ROOT
    print(f"\n==> Running: {' '.join(cmd)} (cwd={workdir})")
    subprocess.run(cmd, cwd=workdir, check=True)
def run_vivado_cmd(command: str, vivado_settings: Path | None) -> None:
    tool = command.split()[0]
    if shutil.which(tool) is not None and vivado_settings is None:
        run_cmd(shlex.split(command))
        return

    if not vivado_settings:
        raise FileNotFoundError(
            f"{tool} not found on PATH. Provide --vivado-settings or run from a Vivado shell."
        )

    settings_path = vivado_settings
    suffix = settings_path.suffix.lower()
    if suffix == ".bat":
        run_cmd(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                f'& "{settings_path}" ; {command}',
            ]
        )
    elif suffix in {".sh", ".bash"}:
        run_cmd(
            ["bash", "-lc", f'source "{settings_path}" && {command}']
        )
    else:
        raise ValueError(
            f"Unsupported settings script extension: {settings_path.suffix}. "
            "Use .bat (Windows) or .sh/.bash (bash)."
        )


def parse_flopoco_metadata(vhdl_path: Path) -> dict[str, int | str]:
    text = vhdl_path.read_text(encoding="utf-8")
    entity_match = re.search(r"entity\s+(\w+)\s+is", text, re.IGNORECASE)
    if not entity_match:
        raise RuntimeError("Unable to find entity name in flopoco.vhdl")
    entity_name = entity_match.group(1)

    def vector_width(signal_name: str) -> int:
        pattern = (
            rf"{signal_name}\s*:\s*(?:in|out)\s+std_logic_vector\((\d+)\s+downto\s+(\d+)\)"
        )
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            raise RuntimeError(f"Unable to parse width for {signal_name}")
        hi, lo = map(int, match.groups())
        return hi - lo + 1

    x_width = vector_width("X")
    y_width = vector_width("Y")

    lsb_match = re.search(r"lsbIn=([-]?\d+).*?lsbOut=([-]?\d+)", text, re.IGNORECASE | re.DOTALL)
    if not lsb_match:
        raise RuntimeError("Unable to find lsbIn/lsbOut in FloPoCo comments")
    lsb_in, lsb_out = map(int, lsb_match.groups())

    msb_match = re.search(r"msbout=([-]?\d+)", text, re.IGNORECASE)
    if not msb_match:
        raise RuntimeError("Unable to find msbout in FloPoCo comments")
    msb_out = int(msb_match.group(1))

    return {
        "entity": entity_name,
        "x_width": x_width,
        "y_width": y_width,
        "lsb_in": lsb_in,
        "lsb_out": lsb_out,
        "msb_out": msb_out,
    }


def update_tb(tb_path: Path, x_width: int, y_width: int) -> None:
    text = tb_path.read_text(encoding="utf-8")
    x_pattern = r"signal\s+x_tb\s*:\s*std_logic_vector\(\d+\s+downto\s+0\)"
    y_pattern = r"signal\s+y_tb\s*:\s*std_logic_vector\(\d+\s+downto\s+0\)"
    text, n1 = re.subn(
        x_pattern,
        f"signal x_tb     : std_logic_vector({x_width - 1} downto 0)",
        text,
        count=1,
    )
    text, n2 = re.subn(
        y_pattern,
        f"signal y_tb     : std_logic_vector({y_width - 1} downto 0)",
        text,
        count=1,
    )
    if n1 != 1 or n2 != 1:
        raise RuntimeError("Failed to update TB signal widths.")

    sweep_count = 1 << x_width
    loop_pattern = r"for\s+in_value\s+in\s+0\s+to\s+\d+\s+loop"
    text, n3 = re.subn(
        loop_pattern,
        f"for in_value in 0 to {sweep_count - 1} loop",
        text,
        count=1,
    )
    report_pattern = r'report "Sweeping all .*? input vectors'
    text, n4 = re.subn(
        report_pattern,
        f'report "Sweeping all {sweep_count} input vectors',
        text,
        count=1,
    )
    if n3 != 1 or n4 != 1:
        raise RuntimeError("Failed to update TB sweep information.")

    tb_path.write_text(text, encoding="utf-8")
    print(f"Updated {tb_path} to X={x_width} bits, Y={y_width} bits.")


def update_verifier(script_path: Path, lsb_in: int, lsb_out: int) -> None:
    text = script_path.read_text(encoding="utf-8")
    text, n1 = re.subn(r"LSB_IN\s*=\s*[-]?\d+", f"LSB_IN = {lsb_in}", text, count=1)
    text, n2 = re.subn(r"LSB_OUT\s*=\s*[-]?\d+", f"LSB_OUT = {lsb_out}", text, count=1)
    if n1 != 1 or n2 != 1:
        raise RuntimeError("Failed to update verifier script LSBs.")
    script_path.write_text(text, encoding="utf-8")
    print(f"Updated {script_path} with LSB_IN={lsb_in}, LSB_OUT={lsb_out}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate FloPoCo → Vivado flow.")
    parser.add_argument("--flopoco-dir", type=Path, default=DEFAULT_FLOPOCO_DIR)
    parser.add_argument("--docker-tag", default="flopoco:debian-5.0.0")
    parser.add_argument("--function", default='log(x+0.0001)/log(2)')
    parser.add_argument("--lsb-in", type=int, default=-6)
    parser.add_argument("--lsb-out", type=int, default=-6)
    parser.add_argument("--frequency", type=int, default=1)
    parser.add_argument("--target", default="Kintex7")
    parser.add_argument("--part", default="xc7k70tfbg484-3")
    parser.add_argument(
        "--extra-flopoco-args",
        default="ilpTimeout=300 compression=optimal_minStages "
        "tiling=optimalTilingAndCompression useTargetOpt=1",
    )
    args = parser.parse_args()

    flopoco_dir = args.flopoco_dir.resolve()
    if not flopoco_dir.exists():
        raise FileNotFoundError(f"FloPoCo directory not found: {flopoco_dir}")

    mount_path = str(flopoco_dir).replace("\\", "/")
    extra_args = shlex.split(args.extra_flopoco_args)
    print(f"Function: {args.function}")
    print(f"LSB in: {args.lsb_in}")
    print(f"LSB out: {args.lsb_out}")
    print(f"Frequency: {args.frequency}")
    print(f"Target: {args.target}")
    print(f"Part: {args.part}")
    print(f"Extra Flopoco args: {args.extra_flopoco_args}")
    print(f"Docker tag: {args.docker_tag}")
    print(f"Flopoco dir: {flopoco_dir}")
    print(f"Mount path: {mount_path}")
    print(f"Extra args: {extra_args}")
    flopoco_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{mount_path}:/flopoco_workspace",
        args.docker_tag,
        "FixFunctionByTable",
        f"f={args.function}",
        f"lsbIn={args.lsb_in}",
        f"lsbOut={args.lsb_out}",
        f"target={args.target}",
        f"frequency={args.frequency}",
    ]
    flopoco_cmd.extend(extra_args)
    run_cmd(flopoco_cmd, cwd=flopoco_dir)

    generated_vhdl = flopoco_dir / "flopoco.vhdl"
    if not generated_vhdl.exists():
        raise FileNotFoundError(f"Generated flopoco.vhdl not found in {flopoco_dir}")

    dest_vhdl = PY_SCRIPTS_ROOT / "hdl" / "flopoco.vhdl"
    shutil.copy2(generated_vhdl, dest_vhdl)
    print(f"Copied {generated_vhdl} -> {dest_vhdl}")

    metadata = parse_flopoco_metadata(dest_vhdl)
    top_entity = metadata["entity"]
    x_width = metadata["x_width"]
    y_width = metadata["y_width"]
    lsb_in = metadata["lsb_in"]
    lsb_out = metadata["lsb_out"]
    msb_out = metadata["msb_out"]
    print(
        "Parsed FloPoCo metadata:",
        f"entity={top_entity}, X width={x_width}, Y width={y_width},",
        f"lsb_in={lsb_in}, msb_out={msb_out}, lsb_out={lsb_out}",
    )

    update_tb(PY_SCRIPTS_ROOT / "tb_FixFunctionByTable.vhdl", x_width, y_width)
    update_verifier(PY_SCRIPTS_ROOT / "verify_fixfunction_outputs.py", lsb_in, lsb_out)

    call_vivado_cmd = [
        "python",
        "call_vivado.py",
        "--tcl",
        "project_free_flow.tcl",
        "--args",
        args.part,
        top_entity,
        "./hdl",
        "./build",
        "./constraints/top.xdc",
    ]
    run_cmd(call_vivado_cmd)

    run_cmd(["python", "read_util_report.py", "build/reports/util_post_route.rpt"])

    tb_entity = "FixFunctionByTable_tb"
    snapshot = f"{tb_entity}_sim"
    # Hardcoded Vivado settings path
    vivado_settings_path = Path(r"D:\Xilinx\2025.1.1\Vivado\settings64.bat").resolve()
    if not vivado_settings_path.exists():
        raise FileNotFoundError(
            f"Vivado settings file not found at {vivado_settings_path}. "
            "Please update the path in automate_flow.py"
        )

    run_vivado_cmd("xvhdl -nolog hdl/flopoco.vhdl tb_FixFunctionByTable.vhdl", vivado_settings_path)
    run_vivado_cmd(f"xelab -nolog {tb_entity} -s {snapshot}", vivado_settings_path)
    run_vivado_cmd(f"xsim --nolog {snapshot} --runall", vivado_settings_path)
    
    # Clean up journal and project build files created by Vivado tools
    for pattern in ["*.jou", "*.pb", "xsim*.jou", "xsim*.backup.jou", "xvhdl*.jou", "xelab*.jou"]:
        for file_path in PY_SCRIPTS_ROOT.glob(pattern):
            try:
                file_path.unlink()
            except OSError:
                pass  # Ignore errors if file doesn't exist or can't be deleted

    verify_cmd = [
        "python",
        "verify_fixfunction_outputs.py",
        "simulation/FixFunctionByTable_outputs.csv",
        "--lsb-in",
        str(lsb_in),
        "--lsb-out",
        str(lsb_out),
        "--function",
        args.function,
    ]
    run_cmd(verify_cmd)

    compute_errors_cmd = [
        "python",
        "compute_errors.py",
        "--csv",
        "simulation/FixFunctionByTable_outputs.csv",
        "--lsb-in",
        str(lsb_in),
        "--msb-out",
        str(msb_out),
        "--lsb-out",
        str(lsb_out),
        "--function",
        args.function,
    ]
    run_cmd(compute_errors_cmd)


if __name__ == "__main__":
    main()

