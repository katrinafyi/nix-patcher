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

def log(*args):
  print(*args, file=sys.stderr, flush=True)

patch2pr = shutil.which('patch2pr')
if not patch2pr:
  gopath = subprocess.check_output(['go', 'env', 'GOPATH'], text=True).strip()
  patch2pr = gopath + '/bin/patch2pr'
patch2pr = Path(patch2pr)
assert patch2pr.exists(), "patch2pr not found!"


@dataclasses.dataclass
class Repo:
  input: str = '' # flake input name
  upstream: str = '' # owner/repo
  revision: str = '' # revision hash

  fork: str = '' # owner/repo
  branch: str = '' # patch branch
  patches: list[tuple[int, str, str]] = dataclasses.field(default_factory=list)


def main(argv):
  argp = argparse.ArgumentParser('nix flake update with patches.')
  argp.add_argument('--flake', '-f', default='.', type=str, 
                    help='flake reference')
  argp.add_argument('--patched-suffix', default='-patched', type=str)
  argp.add_argument('--patch-suffix', default='-patch-', type=str)
  argp.add_argument('--print', action='store_true',
                    help='print detected patch information without applying')
  argp.add_argument('--tmp', default=tempfile.gettempdir())

  args = argp.parse_args(argv[1:])
  args.tmp = Path(tempfile.mkdtemp(dir=args.tmp))
  log(args)

  flakemeta = subprocess.check_output(
    ['nix', 'flake', 'metadata', '--json', args.flake],
    text=True).strip()
  flakemeta = json.loads(flakemeta)
  locks = flakemeta['locks']

  flakepath = flakemeta["resolvedUrl"]
  log(f'{flakepath=}')

  repos = collections.defaultdict(Repo)

  for k, v in locks['nodes'].items():
    original = v.get('original')
    locked = v.get('locked')
    if not locked: continue # "root" object

    if k.endswith(args.patched_suffix):
      name = k[:len(k)-len(args.patched_suffix)]

      repos[name].fork = f"{locked['owner']}/{locked['repo']}"
      repos[name].branch = original['ref']
    elif (split := k.rsplit(args.patch_suffix, 1)) and len(split) == 2:
      name, num = split
      try: num = int(num)
      except ValueError: num = None
      if num is not None:
        # from lv.cha on discord
        path = subprocess.check_output(
          ['nix', 'eval', '--impure', '--expr',
           f'(builtins.getFlake "{flakepath}").inputs.{k}.outPath'])
        path = json.loads(path)

        patch = (num, locked['url'], path)
        repos[name].patches.append(patch)
    elif 'repo' in locked:
      # if earlier checks did not match, assume this is a
      # base (upstream) repository
      repos[k].input = k
      repos[k].upstream = f"{locked['owner']}/{locked['repo']}"
      repos[k].revision = locked['rev']
 
  if args.print:
    asdict = {k: dataclasses.asdict(v) for k,v in repos.items()}
    json.dump(asdict, sys.stdout, indent=2)
    return

  log(f'{patch2pr=}')
  for repo in repos.values():
    if not (repo.input and repo.fork and repo.patches):
      log(repo.input, ': skipping input', repo)
      continue

    log(repo.input, ': fork is', repo.fork, 'branch', repo.branch)
    repo.patches.sort(key=lambda x: x[0])
    rev = repo.revision
    for i, url, p in repo.patches:
      log(repo.input, f': applying patch {i}', p)
      out = subprocess.check_output([
        patch2pr,
        '-repository', repo.fork,
        '-patch-base', rev,
        '-head-branch', repo.branch,
        '-no-pull-request',
        '-force',
        '-json', p
      ])
      out = json.loads(out)
      rev = out['commit']
      log(repo.input, ': ->', out)

    log(repo.input, ': final commit:', rev)
    log(repo.input, ':', f'https://github.com/{repo.fork}/tree/{repo.branch}')
    log(repo.input, ':', f'https://github.com/{repo.fork}/commit/{rev}')

if __name__ == '__main__':
  sys.exit(main(sys.argv))
