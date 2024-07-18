> ⚠️ This tool has not been tested through consistent use, not even by myself.
> If you're interested in it, though, please give it a try and let me know if it fails.
> I will work to fix any issues.


# nix-patcher

_nix-patcher_ is a tool for patching Nix flake inputs.
It semi-automatically maintains a forked nixpkgs with any number of patches applied.
Configuration of the upstream repository, fork repository, and patch files are all done
within flake.nix.

For example, given these inputs (fixed for reproducibility),
```nix
inputs.nixpkgs-upstream.url = "github:nixos/nixpkgs/f9d39fb9aff0efee4a3d5f4a6d7c17701d38a1d8";

inputs.nixpkgs.url = "github:katrinafyi/nixpkgs/patch-branch";  # XXX change me!

inputs.nixpkgs-patch-10.url = "https://github.com/NixOS/nixpkgs/compare/ffacc011dffba16ca360028d1f81cae99ff1280f..9a9cf8661391f21f7a44dc4823f815524351c94f.patch";
inputs.nixpkgs-patch-10.flake = false;
inputs.nixpkgs-patch-20.url = "https://github.com/NixOS/nixpkgs/commit/c22a75b70ffe390f4ef3cc3a63eae5fcd5861779.patch";
inputs.nixpkgs-patch-20.flake = false;
```
nix-patcher will notice the special "-upstream" and "-patch-" suffixes and match these with "nixpkgs-upstream".
When run, the repo and branch to update will be taken from the "nixpkgs" inputs.
The upstream, patches, and fork inputs are linked together by their common prefix (here, "nixpkgs").

By default, the patched input has no suffix - we assume it will be used most often but this can be configured.
Patch numbers need not be contiguous as they are only used to determine patch order.
It is also permitted to have no patch inputs.
The fork repository must be hosted on Github since we make use of Github's API to
perform the patch without a checkout of nixpkgs.

## usage

### first time

To set this up, you'll need to add the upstream and patch inputs to your flake.nix.
After this, run `nix flake lock` to generate their lock entries
(The patched fork and its branch must exist! Create them manually if not.).
Don't forget to add `...` to your output function's argument list.

For nix-patcher itself, you will need a Github token.
A [fine-grained token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token)
is suggested, and it will need at least write permissions on the fork repository.
If you plan to use this within Github Actions, you can make use of the
[automatic token](https://docs.github.com/en/actions/security-guides/automatic-token-authentication).

Then, simply run nix-patcher from within the flake directory
```bash
GITHUB_TOKEN=... nix run github:katrinafyi/nix-patcher -- --commit
```
If all goes well, it will update and commit the relevant inputs.
Links to the newly-patched branch and the last commit are also printed.

Patching nixpkgs takes around 40 seconds.

### updating inputs

When it comes time to update your upstream, the process is much the same.
First, you can run
```bash
nix flake update
```
This will upgrade all inputs, including upstreams and the patched forks.
Assuming nothing has changed our fork's branch in the meantime, this is perfectly safe.

Then, as before,
```
GITHUB_TOKEN=... nix run github:katrinafyi/nix-patcher -- --commit
```

It is a good idea to perform these two commands as atomically as possible.
For example, do not push any changes unless both commands succeed.
This will ensure the upstream and forked repositories stay in sync in the lock file.

### arguments

```
usage: patcher.py [-h] [--flake FLAKE] [--upstream-suffix UPSTREAM_SUFFIX]
                  [--patched-suffix PATCHED_SUFFIX] [--patch-suffix PATCH_SUFFIX]
                  [--update] [--commit] [--print] [--tmp TMP]

nix-patcher is a tool for patching Nix flake inputs, semi-automatically.

options:
  -h, --help            show this help message and exit
  --flake FLAKE, -f FLAKE
                        flake reference
  --upstream-suffix UPSTREAM_SUFFIX
                        suffix for upstream repositories (default: -upstream)
  --patched-suffix PATCHED_SUFFIX
                        suffix for patched forks (default: '')
  --patch-suffix PATCH_SUFFIX
                        suffix for patch files (default: -patch-)
  --update              if set, will call `nix flake update _` on the newly patched inputs
  --commit              like --update but also adds --commit-lock-file
  --print               print detected patches without applying
  --tmp TMP
```

## closing

We made use of the quite clever [patch2pr] tool to perform
the patching through Github's API.
This enables us to work without any local copies of upstream.

[patch2pr]: https://github.com/bluekeyes/patch2pr

This project was built with 😠.
