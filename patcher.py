#!/usr/bin/env python3
# vim: ts=2 sts=2 et sw=2

import sys
import json
import shutil
import argparse
import tempfile
import subprocess
import collections
import dataclasses

from pathlib import Path

def log(*args, **kwargs):
  print(*args, **kwargs, file=sys.stderr, flush=True)

patch2pr_path = shutil.which('patch2pr')
if not patch2pr_path:
  gopath = subprocess.check_output(['go', 'env', 'GOPATH'], text=True).strip()
  patch2pr_path = gopath + '/bin/patch2pr'
patch2pr = Path(patch2pr_path)
assert patch2pr.exists(), "patch2pr not found!"


@dataclasses.dataclass
class Repo:
  basename: str = '' # flake input name
  upstream: str = '' # owner/repo
  revision: str = '' # revision hash of patch base

  fork: str = '' # owner/repo
  branch: str = '' # branch to use for patch
  patches: list[tuple[int, str, str]] = dataclasses.field(default_factory=list)
  final: str = ''

# apply the given patch to the given fork repo and
# return the new commit hash
def apply_patch(fork: str, base: str, branch: str, patch: str, dry: bool):
  if dry:
    log('... dry run, skipping patch apply')
    split = base.split('_') + ['0']
    commit, n = split[:2]
    return commit + '_' + str(int(n)+1)
  out = subprocess.check_output([
    patch2pr,
    '-repository', fork,
    '-patch-base', base,
    '-head-branch', branch,
    '-no-pull-request',
    '-force',
    '-json', patch
  ])
  out = json.loads(out)
  return out['commit']


def main(argv):
  argp = argparse.ArgumentParser(description='nix-patcher is a tool for patching Nix flake inputs, semi-automatically.')
  argp.add_argument('--flake', '-f', default='.', type=str, 
                    help='flake reference')
  argp.add_argument('--upstream-suffix', default='-upstream', type=str,
                    help='suffix for upstream repositories (default: -upstream)')
  argp.add_argument('--patched-suffix', default='', type=str,
                    help='suffix for patched forks (default: \'\')')
  argp.add_argument('--patch-suffix', default='-patch-', type=str,
                    help='suffix for patch files (default: -patch-)')
  argp.add_argument('--update', action='store_true',
                    help='if set, will call `nix flake update _` on the newly patched inputs')
  argp.add_argument('--commit', action='store_true',
                    help='like --update but also adds --commit-lock-file')
  argp.add_argument('--dry-run', action='store_true',
                    help='log steps but do not perform any changes')
  argp.add_argument('--verbose', action='store_true',
                    help='print additional state information')

  args = argp.parse_args(argv[1:])
  args.update |= args.commit

  if args.upstream_suffix == args.patched_suffix:
    argp.error('upstream and patched suffixes must not be identical.')
  if not args.patch_suffix:
    argp.error('patch suffix must not be empty')

  flakemeta = subprocess.check_output(
    ['nix', 'flake', 'metadata', '--json', args.flake],
    text=True).strip()
  flakemeta = json.loads(flakemeta)
  locks = flakemeta['locks']

  flakepath = flakemeta["resolvedUrl"]
  log(f'{flakemeta["resolvedUrl"]=}')

  repos = collections.defaultdict(Repo)

  # restrict using locks.root.inputs to only
  # handle inputs occuring in /this/ flake, and
  # not transitive inputs
  rootkey = locks['root']
  for k in locks['nodes'][rootkey]['inputs'].keys():
    v = locks['nodes'][k]
    original = v.get('original')
    locked = v.get('locked')
    # log(locked)
    if not locked: continue # "root" object

    # if both suffixes match, select the longer one
    is_patched = k.endswith(args.patched_suffix)
    is_upstream = k.endswith(args.upstream_suffix)
    is_patch = None
    if is_patched and is_upstream:
      is_patched = len(args.patched_suffix) > len(args.upstream_suffix)
      is_upstream = len(args.upstream_suffix) > len(args.patched_suffix)
      assert is_patched != is_upstream, "logic error, equal suffixes??"


    if (split := k.rsplit(args.patch_suffix, 1)) and len(split) == 2:
      name, num = split
      try: num = int(num)
      except ValueError: num = None
      if num is not None:
        is_patch = (name, num)

    log(f'parsing {k=}', f'{is_upstream=}', f'{is_patched=}', f'{is_patch=}', sep=', ')

    if is_patch:
      name, num = is_patch
      # via lv.cha on discord
      path = subprocess.check_output(
        ['nix', 'eval', '--impure', '--expr',
         f'(builtins.getFlake "{flakepath}").inputs.{k}.outPath'])
      path = json.loads(path)

      patch = (num, locked['url'], path)
      repos[name].patches.append(patch)

    elif is_patched:
      name = k[:len(k)-len(args.patched_suffix)]
      if not original.get('ref'):
        log(name, ': ignoring input despite patched-suffix match, due to no branch specified')
        continue
      repos[name].fork = f"{original['owner']}/{original['repo']}"
      repos[name].branch = original['ref']

    elif is_upstream:
      name = k[:len(k)-len(args.upstream_suffix)]
      repos[name].basename = name
      repos[name].upstream = f"{locked['owner']}/{locked['repo']}"
      repos[name].revision = locked['rev']

  if args.verbose:
    asdict = {k: dataclasses.asdict(v) for k,v in repos.items()}
    json.dump(asdict, sys.stderr, indent=2)
    print(file=sys.stderr)

  log(f'{patch2pr=}')
  for repo in repos.values():
    if not (repo.basename and repo.fork):
      log(repo.basename, ': skipping input (missing upstream or fork):', repo)
      continue

    log(repo.basename, ': patching. fork is', f'{repo.fork=}', f'{repo.branch=}')
    repo.patches.sort(key=lambda x: x[0])
    rev = repo.revision
    for i, url, p in repo.patches:
      log(repo.basename, f': applying patch {i}: {p!s}')
      rev = apply_patch(repo.fork, rev, repo.branch, p, args.dry_run)
      log(repo.basename, ': ->', rev)

    repo.final = rev
    log(repo.basename, ': final commit:', rev)
    log(repo.basename, ':', f'https://github.com/{repo.fork}/tree/{repo.branch}')
    log(repo.basename, ':', f'https://github.com/{repo.fork}/commit/{rev}')

  if args.update:
    def patched(repo): return repo.basename + args.patched_suffix
    update_cmd = [[patched(repo), '--override-input', patched(repo), f'github:{repo.fork}/{repo.final}'] for repo in repos.values() if repo.final]
    update_cmd = [x for y in update_cmd for x in y]

    if update_cmd:
      if args.commit:
        update_cmd = ['--commit-lock-file'] + update_cmd

      log(f'{update_cmd=}')
      if not args.dry_run:
        subprocess.check_call(['nix', 'flake', 'update', '--flake', flakepath] + update_cmd)

if __name__ == '__main__':
  sys.exit(main(sys.argv))
