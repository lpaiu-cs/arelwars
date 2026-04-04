/*
 * AW2 Worldmap Runtime Trace Library
 *
 * Loaded via System.loadLibrary in the patched APK.
 * Polls 9 key memory fields of CPdStateWorldmap and logs changes to logcat.
 *
 * The binary patch in DoTouchMoveWorldArea stores:
 *   - wm_this (r0)            at libgameDSO.so + 0x21c934
 *   - global_holder_ptr (r3)  at libgameDSO.so + 0x21c938
 * On every call. The global_holder_ptr is dereferenced once to get globalPtr.
 */

#include <android/log.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define TAG "AW2TRACE"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

#define BSS_THIS_OFF   0x21c934
#define BSS_HOLDER_OFF 0x21c938

typedef struct {
    uint8_t  g58;
    uint8_t  g1068;
    uint8_t  t200;
    int32_t  t100;
    uint8_t  tfc;
    uint8_t  tfd;
    int32_t  t36f0;
    uint8_t  t379c;
    int32_t  t36f8;
    uint8_t  t362c;
    int32_t  t8;
} snap_t;

static uintptr_t find_module_base(const char *name) {
    char line[512];
    FILE *f = fopen("/proc/self/maps", "r");
    if (!f) return 0;
    uintptr_t base = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strstr(line, name)) {
            base = (uintptr_t)strtoul(line, NULL, 16);
            break;
        }
    }
    fclose(f);
    return base;
}

static void read_snap(snap_t *s, uintptr_t gp, uintptr_t tp) {
    s->g58    = *(volatile uint8_t *)(gp + 0x58);
    s->g1068  = *(volatile uint8_t *)(gp + 0x1068);
    s->t200   = *(volatile uint8_t *)(tp + 0x200);
    s->t100   = *(volatile int32_t *)(tp + 0x100);
    s->tfc    = *(volatile uint8_t *)(tp + 0xfc);
    s->tfd    = *(volatile uint8_t *)(tp + 0xfd);
    s->t36f0  = *(volatile int32_t *)(tp + 0x36f0);
    s->t379c  = *(volatile uint8_t *)(tp + 0x379c);
    s->t36f8  = *(volatile int32_t *)(tp + 0x36f8);
    s->t362c  = *(volatile uint8_t *)(tp + 0x362c);
    s->t8     = *(volatile int32_t *)(tp + 8);
}

static void log_snap(const char *label, const snap_t *s) {
    LOGI("%s g58=%d g1068=%d t200=%d t100=%d tfc=%d tfd=%d "
         "t36f0=%d t379c=%d t36f8=%d t362c=%d state=%d",
         label, s->g58, s->g1068, s->t200, s->t100,
         s->tfc, s->tfd, s->t36f0, s->t379c,
         s->t36f8, s->t362c, s->t8);
}

static void *poll_thread(void *arg) {
    (void)arg;
    LOGI("Poll thread started, waiting for libgameDSO.so...");

    uintptr_t base = 0;
    while (!base) {
        base = find_module_base("libgameDSO.so");
        if (!base) usleep(500000);
    }
    LOGI("libgameDSO.so base: %p", (void *)base);

    volatile uint32_t *this_slot   = (volatile uint32_t *)(base + BSS_THIS_OFF);
    volatile uint32_t *holder_slot = (volatile uint32_t *)(base + BSS_HOLDER_OFF);

    /* Resolve globalPtr directly from GOT chain to read 0x1068 immediately.
     * From DoTouchMoveWorldArea disasm:
     *   pool_A @ base+0x10a568, pool_B @ base+0x10a56c
     *   r7 = pool_A + (base + 0x10a31e)
     *   r3 = *(r7 + pool_B)   <-- GOT entry holding ptr-to-globalPtr
     *   globalPtr = *r3
     */
    {
        uint32_t pool_A = *(volatile uint32_t *)(base + 0x10a568);
        uint32_t pool_B = *(volatile uint32_t *)(base + 0x10a56c);
        uintptr_t r7 = pool_A + base + 0x10a31e;
        uint32_t *holder = (uint32_t *)(r7 + pool_B);
        uintptr_t gp = (uintptr_t)*holder;
        LOGI("GOT-chain: pool_A=0x%x pool_B=0x%x holder=%p globalPtr=%p",
             pool_A, pool_B, holder, (void *)gp);
        if (gp) {
            uint8_t g58   = *(volatile uint8_t *)(gp + 0x58);
            uint8_t g1068 = *(volatile uint8_t *)(gp + 0x1068);
            LOGI("EARLY READ: global+0x58=%d global+0x1068=%d", g58, g1068);
            if (g1068 != 0) {
                LOGI("global+0x1068 is NONZERO (%d) -- forcing to 0 to unlock input", g1068);
                *(volatile uint8_t *)(gp + 0x1068) = 0;
            }
        }
    }

    LOGI("Waiting for DoTouchMoveWorldArea to fill trace slots...");
    int wait_count = 0;
    while (!*this_slot || !*holder_slot) {
        usleep(500000);
        wait_count++;
        if (wait_count % 4 == 0) {
            /* Re-read 0x1068 every 2s to track changes */
            uint32_t pool_A = *(volatile uint32_t *)(base + 0x10a568);
            uint32_t pool_B = *(volatile uint32_t *)(base + 0x10a56c);
            uintptr_t r7 = pool_A + base + 0x10a31e;
            uint32_t *holder = (uint32_t *)(r7 + pool_B);
            uintptr_t gp = (uintptr_t)*holder;
            if (gp) {
                uint8_t g1068 = *(volatile uint8_t *)(gp + 0x1068);
                uint8_t g58   = *(volatile uint8_t *)(gp + 0x58);
                if (g1068 != 0) {
                    LOGI("POLL %ds: global+0x1068=%d -- forcing to 0",
                         wait_count / 2, g1068);
                    *(volatile uint8_t *)(gp + 0x1068) = 0;
                } else {
                    LOGI("POLL %ds: g58=%d g1068=%d this_slot=0x%x",
                         wait_count / 2, g58, g1068, *this_slot);
                }
            } else {
                LOGI("Still waiting (%ds)... this_slot=0x%x holder_slot=0x%x",
                     wait_count / 2, *this_slot, *holder_slot);
            }
        }
    }

    uintptr_t wm_this = (uintptr_t)*this_slot;
    uintptr_t holder  = (uintptr_t)*holder_slot;
    uintptr_t gp      = *(volatile uint32_t *)holder;  /* dereference holder -> globalPtr */

    LOGI("wm_this=%p holder=%p globalPtr=%p", (void *)wm_this, (void *)holder, (void *)gp);

    snap_t prev;
    memset(&prev, 0, sizeof(prev));
    read_snap(&prev, gp, wm_this);
    log_snap("INIT", &prev);

    int idle = 0;
    while (1) {
        /* Re-read wm_this in case a new worldmap instance was created */
        uintptr_t cur_this = (uintptr_t)*this_slot;
        if (cur_this != wm_this) {
            wm_this = cur_this;
            LOGI("wm_this changed to %p", (void *)wm_this);
        }
        /* Re-read globalPtr in case it changed */
        uintptr_t cur_gp = *(volatile uint32_t *)holder;
        if (cur_gp != gp) {
            gp = cur_gp;
            LOGI("globalPtr changed to %p", (void *)gp);
        }

        /* Keep 0x1068 at 0 -- re-assert every iteration */
        if (*(volatile uint8_t *)(gp + 0x1068) != 0) {
            LOGI("0x1068 reasserted! forcing back to 0");
            *(volatile uint8_t *)(gp + 0x1068) = 0;
        }

        snap_t cur;
        read_snap(&cur, gp, wm_this);
        if (memcmp(&cur, &prev, sizeof(snap_t)) != 0) {
            log_snap("CHANGE", &cur);
            prev = cur;
            idle = 0;
        } else {
            idle++;
            /* After 1s of no change, slow down polling */
            if (idle > 125) {
                usleep(50000); /* 50ms */
            }
        }
        usleep(8000); /* ~8ms base rate */
    }
    return NULL;
}

__attribute__((constructor))
static void trace_init(void) {
    LOGI("=== AW2 Worldmap Trace Library loaded ===");
    pthread_t t;
    pthread_create(&t, NULL, poll_thread, NULL);
    pthread_detach(t);
}
