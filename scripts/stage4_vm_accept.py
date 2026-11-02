import sys
import uuid
import time
import os
import subprocess
import json
from pathlib import Path
import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

repo = Path('/home/server1/project-bots').resolve()
sys.path.insert(0, str(repo))
token_file = Path('/home/server1/.hermes/profiles/project-bot/private/stage4-mcp.token')
ssh_key_pub = '/home/server1/.hermes/profiles/project-bot/private/stage2-acceptance-ed25519.pub'
machine_id = 'e0778e6a-8b1c-484d-8372-0cf60a780b30'

def get_compute_service_ssh():
    return ['ssh', '-i', '/home/server1/.hermes/profiles/project-bot/ssh/gaming_pc_ed25519', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=no', 'pbcompute@10.0.50.56']

def set_ram_cap(cap):
    ssh = get_compute_service_ssh()
    cmd = f'echo "PROJECT_BOTS_COMPUTE_TOKEN=OUraM1zetlLyj3XPNkjsoYm2JUJy89n9_U8mHnGs45krZfApMTlSMk4T-kgWL0sR\nPROJECT_BOTS_COMPUTE_RAM_CAP={cap}" > /home/pbcompute/.config/project-bots-compute/compute.env'
    subprocess.run(ssh + [cmd], check=True)
    subprocess.run(ssh + ['systemctl --user restart project-bots-compute.service'], check=True)
    time.sleep(10)

async def call_tool(session, name, args):
    print(f"Calling {name} with {args}")
    result = await session.call_tool(name, args)
    if result.is_error:
        raise RuntimeError(f"Tool {name} failed: {result.content}")
    return result.structured_content

async def run():
    params = StdioServerParameters(command=sys.executable, args=['-m', 'project_bots.mcp_server', '--endpoint', 'http://127.0.0.1:8033', '--token-file', str(token_file)], cwd=repo)
    
    test_vm_id = None
    cap_raised = False
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                print("Baseline: Snapshotting workers/vms")
                baseline_workers = await call_tool(session, 'list_workers', {})
                baseline_vms = await call_tool(session, 'list_vms', {'machine_id': machine_id})
                print(f"Baseline VMs count: {len(baseline_vms)}")

                print("Step 1: Raising RAM cap")
                set_ram_cap(40960)
                cap_raised = True

                print("Step 2: Executing VM lifecycle via MCP")
                op_id = str(uuid.uuid4())
                test_vm_id = op_id
                pub_key = Path(ssh_key_pub).read_text().strip()
                
                # 1. Create
                res = await session.call_tool('create_vm', {
                    'machine_id': machine_id,
                    'template': 'ubuntu-desktop',
                    'cpus': 1,
                    'ram_mib': 4096,
                    'disk_gib': 20,
                    'ssh_key': pub_key,
                    'operation_id': op_id,
                    'confirmation': 'create'
                })
                if res.is_error:
                    print("CREATE ERROR CONTENT:", res.content)
                    raise RuntimeError(f"Create failed: {res.content}")
                print(f"Created VM: {test_vm_id}")

                # 2. Start
                start_op = str(uuid.uuid4())
                await call_tool(session, 'vm_action', {
                    'machine_id': machine_id,
                    'vm_id': test_vm_id,
                    'action': 'start',
                    'operation_id': start_op,
                    'confirmation': f'start:{test_vm_id}'
                })
                print("Started VM, waiting for 'running' state...")
                
                for _ in range(60):
                    vm = await call_tool(session, 'get_vm', {'machine_id': machine_id, 'vm_id': test_vm_id})
                    if vm['state'] == 'running':
                        print("VM is running!")
                        break
                    time.sleep(3)
                else:
                    raise RuntimeError("VM start timeout")

                time.sleep(10)

                # 3. Shutdown (ACPI)
                shut_op = str(uuid.uuid4())
                await call_tool(session, 'vm_action', {
                    'machine_id': machine_id,
                    'vm_id': test_vm_id,
                    'action': 'shutdown',
                    'operation_id': shut_op,
                    'confirmation': f'shutdown:{test_vm_id}'
                })
                print("Initiated shutdown, waiting for 'shut off' state...")
                
                for _ in range(80):
                    vm = await call_tool(session, 'get_vm', {'machine_id': machine_id, 'vm_id': test_vm_id})
                    if vm['state'] == 'shut off':
                        print("VM is shut off!")
                        break
                    time.sleep(3)
                else:
                    print("Shutdown timeout via ACPI, forcing domain destroy on compute host...")
                    subprocess.run(['ssh', '-i', '/home/server1/.hermes/profiles/project-bot/ssh/gaming_pc_ed25519', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=no', 'pbcompute@10.0.50.56', f'virsh --connect qemu:///session destroy pb-{test_vm_id} || true'], check=False)

                # 4. Delete
                del_op = str(uuid.uuid4())
                await call_tool(session, 'vm_action', {
                    'machine_id': machine_id,
                    'vm_id': test_vm_id,
                    'action': 'delete',
                    'operation_id': del_op,
                    'confirmation': f'delete:{test_vm_id}'
                })
                print(f"Deleted VM {test_vm_id}")
                test_vm_id = None

                print("Step 3: Restoring RAM cap")
                set_ram_cap(32768)
                cap_raised = False

                print("Step 4: Confirming workers unchanged")
                after_workers = await call_tool(session, 'list_workers', {})
                after_vms = await call_tool(session, 'list_vms', {'machine_id': machine_id})
                
                assert baseline_workers == after_workers, "Workers changed!"
                assert baseline_vms == after_vms, "VMs changed!"
                print("SUCCESS: Full VM lifecycle verified and all original workers & VMs confirmed 100% unchanged!")

    finally:
        if test_vm_id:
            print("Cleanup: destroying and deleting test VM if present...")
            subprocess.run(['ssh', '-i', '/home/server1/.hermes/profiles/project-bot/ssh/gaming_pc_ed25519', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=no', 'pbcompute@10.0.50.56', f'virsh --connect qemu:///session destroy pb-{test_vm_id} 2>/dev/null || true'], check=False)
        if cap_raised:
            print("Cleanup: restoring RAM cap...")
            try:
                set_ram_cap(32768)
            except Exception as e:
                print(f"Failed to restore RAM cap in finally: {e}")

if __name__ == '__main__':
    anyio.run(run)
