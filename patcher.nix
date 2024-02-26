{ lib
, stdenv
, makeWrapper
, python3
, nix
, patch2pr
}:

let path = lib.makeBinPath [ nix patch2pr ];
in stdenv.mkDerivation {
  pname = "nix-patcher";
  version = "0.1.0";

  src = ./patcher.py;
  dontUnpack = true;

  buildInputs = [ python3 ];
  nativeBuildInputs = [ makeWrapper ];

  installPhase = ''
    mkdir -p $out/bin
    install $src $out/bin/nix-patcher
    wrapProgram $out/bin/* --prefix-each PATH : "${path}"
  '';

  meta = {
    description = "nix-patcher is a tool for patching Nix flake inputs, semi-automatically.";
    homepage = "https://github.com/katrinafyi/nix-patcher";
    mainProgram = "nix-patcher";
  };
}
