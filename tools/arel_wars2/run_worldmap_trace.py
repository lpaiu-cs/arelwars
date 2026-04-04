import frida
import json
import sys
import time
from pathlib import Path

TRACE_LOG = Path(__file__).resolve().parent.parent.parent / "recovery" / "arel_wars2" / "native_tmp" / "worldmap_runtime_trace.jsonl"

script_code = """
let targetModule = "libgameDSO.so";
let moduleBase = NULL;
let globalPtr = NULL;
let wmThisPtr = NULL;
let seqNo = 0;

function dumpState(label, thisPtr, extra) {
    if (globalPtr.isNull() || thisPtr.isNull()) {
        return;
    }
    try {
        let g58 = globalPtr.add(0x58).readU8();
        let g1068 = globalPtr.add(0x1068).readU8();
        let t200 = thisPtr.add(0x200).readU8();
        let t100 = thisPtr.add(0x100).readS32();
        let t36f0 = thisPtr.add(0x36f0).readS32();
        let t379c = thisPtr.add(0x379c).readU8();
        let t36f8 = thisPtr.add(0x36f8).readS32();
        let t362c = thisPtr.add(0x362c).readU8();
        let t8 = thisPtr.add(8).readS32();
        let tfc = thisPtr.add(0xfc).readU8();
        let tfd = thisPtr.add(0xfd).readU8();

        let payload = {
            "global+0x58": g58,
            "global+0x1068": g1068,
            "this+0x200": t200,
            "this+0x100": t100,
            "this+0xfc": tfc,
            "this+0xfd": tfd,
            "this+0x36f0": t36f0,
            "this+0x379c": t379c,
            "this+0x36f8": t36f8,
            "this+0x362c": t362c,
            "this+8 (state)": t8
        };
        if (extra) {
            for (let k in extra) {
                payload[k] = extra[k];
            }
        }

        send({
            type: "trace",
            seq: seqNo++,
            label: label,
            payload: payload
        });
    } catch(e) {
        console.log("Error reading memory: " + e);
    }
}

function hookWorldmap() {
    moduleBase = Module.findBaseAddress(targetModule);
    if (!moduleBase) {
        console.log("Could not find " + targetModule);
        return;
    }
    console.log("[+] libgameDSO.so base: " + moduleBase);

    // ---- 1. OnPointerPress: latch writer + globalPtr resolver ----
    let onPointerPress = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap14OnPointerPressEP12GxPointerPos");
    if (onPointerPress) {
        console.log("[+] Hooking OnPointerPress at " + onPointerPress);

        Interceptor.attach(onPointerPress, {
            onEnter: function(args) {
                this.thisPtr = args[0];
                wmThisPtr = this.thisPtr;
                if (!globalPtr.isNull()) {
                    dumpState("OnPointerPress (Enter)", this.thisPtr);
                }
            },
            onLeave: function(retval) {
                if (!globalPtr.isNull()) {
                    dumpState("OnPointerPress (Leave)", this.thisPtr);
                }
            }
        });

        // Grab globalPtr from r2 at the ldrb r3,[r2,#0x1068] instruction
        let innerAddr = onPointerPress.sub(1).add(0x20);
        Interceptor.attach(innerAddr, {
            onEnter: function(args) {
                if (globalPtr.isNull()) {
                    globalPtr = this.context.r2;
                    console.log("[+] Resolved globalPtr: " + globalPtr);
                }
            }
        });
    } else {
        console.log("[-] Could not find OnPointerPress");
    }

    // ---- 2. OnPointerRelease ----
    let onPointerRelease = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap16OnPointerReleaseEP12GxPointerPos");
    if (onPointerRelease) {
        Interceptor.attach(onPointerRelease, {
            onEnter: function(args) {
                this.thisPtr = args[0];
                dumpState("OnPointerRelease (Enter)", this.thisPtr);
            },
            onLeave: function(retval) {
                dumpState("OnPointerRelease (Leave)", this.thisPtr);
            }
        });
    }

    // ---- 3. DoTouchMoveWorldArea: main dispatcher ----
    let doTouchMove = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap20DoTouchMoveWorldAreaEii");
    if (doTouchMove) {
        Interceptor.attach(doTouchMove, {
            onEnter: function(args) {
                this.thisPtr = args[0];
                let x = args[1].toInt32();
                let y = args[2].toInt32();
                dumpState("DoTouchMoveWorldArea (Enter)", this.thisPtr, {
                    "arg_x": x, "arg_y": y
                });
            },
            onLeave: function(retval) {
                dumpState("DoTouchMoveWorldArea (Leave)", this.thisPtr);
            }
        });
    }

    // ---- 4. TouchGamevilLiveBtns: pre-area swallow detector ----
    let touchLive = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap20TouchGamevilLiveBtnsEii");
    if (touchLive) {
        console.log("[+] Hooking TouchGamevilLiveBtns at " + touchLive);
        Interceptor.attach(touchLive, {
            onEnter: function(args) {
                this.thisPtr = args[0];
                this.x = args[1].toInt32();
                this.y = args[2].toInt32();
            },
            onLeave: function(retval) {
                let rv = retval.toInt32();
                if (rv !== 0) {
                    send({type: "trace", seq: seqNo++,
                          label: "TouchGamevilLiveBtns SWALLOW",
                          payload: {"return": rv, "x": this.x, "y": this.y}});
                }
            }
        });
    } else {
        console.log("[-] Could not find TouchGamevilLiveBtns");
    }

    // ---- 5. InitWorldmapSltAreaAni: 1st tap area selection ----
    let initSlt = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap22InitWorldmapSltAreaAniEi");
    if (initSlt) {
        console.log("[+] Hooking InitWorldmapSltAreaAni at " + initSlt);
        Interceptor.attach(initSlt, {
            onEnter: function(args) {
                let area = args[1].toInt32();
                send({type: "trace", seq: seqNo++,
                      label: "InitWorldmapSltAreaAni (1st tap new area)",
                      payload: {"areaIndex": area}});
            }
        });
    } else {
        console.log("[-] Could not find InitWorldmapSltAreaAni");
    }

    // ---- 6. IsCheckAreaEnter: 2nd tap gate ----
    let isCheck = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap16IsCheckAreaEnterEi");
    if (isCheck) {
        console.log("[+] Hooking IsCheckAreaEnter at " + isCheck);
        Interceptor.attach(isCheck, {
            onEnter: function(args) {
                this.area = args[1].toInt32();
            },
            onLeave: function(retval) {
                let rv = retval.toInt32();
                send({type: "trace", seq: seqNo++,
                      label: "IsCheckAreaEnter (2nd tap gate)",
                      payload: {"areaIndex": this.area, "return": rv}});
            }
        });
    }

    let isCheckFrm = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap23IsCheckAreaEnterFromFrmEi");
    if (isCheckFrm) {
        Interceptor.attach(isCheckFrm, {
            onEnter: function(args) {
                this.area = args[1].toInt32();
            },
            onLeave: function(retval) {
                let rv = retval.toInt32();
                send({type: "trace", seq: seqNo++,
                      label: "IsCheckAreaEnterFromFrm (2nd tap gate)",
                      payload: {"areaIndex": this.area, "return": rv}});
            }
        });
    }

    // ---- 7. UpdateWorldMapMenu: consumer (conditional logging) ----
    let updateMenu = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap18UpdateWorldMapMenuEv");
    if (updateMenu) {
        Interceptor.attach(updateMenu, {
            onEnter: function(args) {
                this.thisPtr = args[0];
                let isInteresting = false;
                try {
                    let t379c = this.thisPtr.add(0x379c).readU8();
                    let t362c = this.thisPtr.add(0x362c).readU8();
                    let t36f8 = this.thisPtr.add(0x36f8).readS32();
                    let state = this.thisPtr.add(8).readS32();
                    if (t379c != 0 || t362c != 0 || t36f8 != -1 || state == 2) {
                        isInteresting = true;
                    }
                } catch(e) {}

                if (isInteresting) {
                    dumpState("UpdateWorldMapMenu (Enter, interesting)", this.thisPtr);
                }
                this.interesting = isInteresting;
            },
            onLeave: function(retval) {
                if (this.interesting) {
                    dumpState("UpdateWorldMapMenu (Leave, interesting)", this.thisPtr);
                }
            }
        });
    }

    // ---- 8. TouchInputWorldFrame: overlay hit detector ----
    let touchFrame = Module.findExportByName(targetModule, "_ZN16CPdStateWorldmap20TouchInputWorldFrameEii");
    if (touchFrame) {
        console.log("[+] Hooking TouchInputWorldFrame at " + touchFrame);
        Interceptor.attach(touchFrame, {
            onLeave: function(retval) {
                let rv = retval.toInt32();
                if (rv !== 0) {
                    send({type: "trace", seq: seqNo++,
                          label: "TouchInputWorldFrame OVERLAY HIT",
                          payload: {"return": rv}});
                }
            }
        });
    }

    console.log("[+] All hooks installed. Ready for trace.");
}

// wait for library to load
let checkInterval = setInterval(function() {
    let base = Module.findBaseAddress(targetModule);
    if (base) {
        clearInterval(checkInterval);
        hookWorldmap();
    }
}, 500);

"""

def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        if payload.get('type') == 'trace':
            label = payload['label']
            seq = payload.get('seq', '?')
            print(f"\n[{seq:>4}] --- {label} ---")
            for k, v in payload['payload'].items():
                print(f"       {k:<20}: {v}")
            # append to jsonl log
            if TRACE_LOG_PATH is not None:
                try:
                    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                except Exception:
                    pass
    else:
        print(f"[*] {message}")

TRACE_LOG_PATH = None

def get_device(mode: str, gadget_host: str | None = None):
    """Return a Frida device based on mode."""
    if mode == "gadget" and gadget_host:
        print(f"Connecting to gadget at {gadget_host}...")
        mgr = frida.get_device_manager()
        return mgr.add_remote_device(gadget_host)
    else:
        print("Connecting to USB device...")
        return frida.get_usb_device()


def trace_app(package_name, mode="usb", gadget_host=None):
    global TRACE_LOG_PATH
    TRACE_LOG_PATH = str(TRACE_LOG)
    TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
    # Clear previous trace
    if TRACE_LOG.exists():
        TRACE_LOG.unlink()
    print(f"Trace log: {TRACE_LOG_PATH}")

    try:
        device = get_device(mode, gadget_host)

        if mode == "gadget":
            # Gadget mode: connect to the single process served by the gadget
            print("Attaching to gadget process...")
            session = device.attach(0)
        else:
            # USB/frida-server mode: find or spawn the app
            pid = None
            for p in device.enumerate_processes():
                if p.name == package_name or p.name == "Arel Wars2":
                    pid = p.pid
                    break

            if not pid:
                print("App not running. Spawning...")
                pid = device.spawn([package_name])
                session = device.attach(pid)
                device.resume(pid)
            else:
                print(f"Attaching to running process {pid}...")
                session = device.attach(pid)

        script = session.create_script(script_code)
        script.on('message', on_message)
        script.load()

        print("\n[!] Tracing started. Navigate to the worldmap, then:")
        print("[!]   1) Tap on a base area (e.g. DESERT PLAIN) -- observe 1st-tap flow")
        print("[!]   2) Tap the SAME area again              -- observe 2nd-tap / enter flow")
        print("[!] Press Ctrl+C to stop tracing.\n")
        sys.stdin.read()
    except KeyboardInterrupt:
        print("\n[!] Tracing stopped.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    import argparse as _ap
    p = _ap.ArgumentParser()
    p.add_argument("--gadget", action="store_true",
                   help="Connect via Frida gadget (port-forwarded) instead of frida-server")
    p.add_argument("--host", default="127.0.0.1:27042",
                   help="Gadget host:port (default: 127.0.0.1:27042)")
    p.add_argument("--package", default="com.gamevil.ArelWars2.global")
    a = p.parse_args()
    if a.gadget:
        trace_app(a.package, mode="gadget", gadget_host=a.host)
    else:
        trace_app(a.package)
