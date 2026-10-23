"""Detect NVIDIA hardware, create a dedicated Conda environment and verify CUDA."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from samstudio.hardware import detect_gpus,conda_gpu_plan

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--name',default='sam-image-studio-gpu');parser.add_argument('--current',action='store_true');parser.add_argument('--sam3',action='store_true');parser.add_argument('--dry-run',action='store_true');parser.add_argument('--inspect',action='store_true');parser.add_argument('--report',type=Path)
    args=parser.parse_args(argv);report=detect_gpus()
    if args.inspect:
        print(json.dumps(report,indent=2));return 0
    try:commands=conda_gpu_plan(ROOT,report,args.name,args.current,args.sam3)
    except ValueError as e:
        print(json.dumps({'status':'unavailable','hardware':report,'reason':str(e)},indent=2));return 2
    result={'status':'planned' if args.dry_run else 'running','hardware':report,'commands':commands,'sam3':args.sam3}
    if args.dry_run:print(json.dumps(result,indent=2));return 0
    for command in commands:
        print('Running: '+' '.join(command),flush=True);subprocess.run(command,cwd=ROOT,check=True)
    result['status']='installed_and_selftest_passed'
    target=args.report or ROOT/'docs/validation/gpu_install_local.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n')
    print('Installation self-test passed. Run python -m samstudio in the activated dedicated environment. Model inference still requires compatible weights and local model acceptance tests.');return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except subprocess.CalledProcessError as error:print('Installation failed; resolve the command error above.',file=sys.stderr);raise SystemExit(error.returncode or 1)
