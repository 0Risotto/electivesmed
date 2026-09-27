{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  packages = with pkgs; [
    python3
    uv
    git
    stdenv.cc.cc.lib
  ];

  shellHook = ''
    export PYTHONPATH="$PWD/src:$PYTHONPATH"
    export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
    if [ ! -d .venv ]; then
      uv venv .venv
    fi
    source .venv/bin/activate
    if ! command -v ho >/dev/null 2>&1; then
      uv pip install -e ".[dev]" -q
    fi
    echo "hospital-outreach shell ready (python $(python -V 2>&1)); try: ho --help"
  '';
}
