#define _GNU_SOURCE

#include <errno.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>
#include <grp.h>

extern char **environ;

#define DENY_SYSCALL(nr) \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (nr), 0, 1), \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | (EPERM & SECCOMP_RET_DATA))

static int install_filter(void) {
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS,
                 (offsetof(struct seccomp_data, arch))),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS,
                 (offsetof(struct seccomp_data, nr))),
        DENY_SYSCALL(__NR_socket),
        DENY_SYSCALL(__NR_socketpair),
        DENY_SYSCALL(__NR_connect),
        DENY_SYSCALL(__NR_accept),
        DENY_SYSCALL(__NR_accept4),
        DENY_SYSCALL(__NR_bind),
        DENY_SYSCALL(__NR_listen),
        DENY_SYSCALL(__NR_sendto),
        DENY_SYSCALL(__NR_recvfrom),
        DENY_SYSCALL(__NR_sendmsg),
        DENY_SYSCALL(__NR_recvmsg),
        DENY_SYSCALL(__NR_shutdown),
        DENY_SYSCALL(__NR_getsockname),
        DENY_SYSCALL(__NR_getpeername),
        DENY_SYSCALL(__NR_setsockopt),
        DENY_SYSCALL(__NR_getsockopt),
        DENY_SYSCALL(__NR_clone),
        DENY_SYSCALL(__NR_clone3),
        DENY_SYSCALL(__NR_fork),
        DENY_SYSCALL(__NR_vfork),
        DENY_SYSCALL(__NR_ptrace),
        DENY_SYSCALL(__NR_process_vm_readv),
        DENY_SYSCALL(__NR_process_vm_writev),
        DENY_SYSCALL(__NR_kill),
        DENY_SYSCALL(__NR_tkill),
        DENY_SYSCALL(__NR_tgkill),
        DENY_SYSCALL(__NR_pidfd_open),
        DENY_SYSCALL(__NR_pidfd_getfd),
        DENY_SYSCALL(__NR_pidfd_send_signal),
        DENY_SYSCALL(__NR_mount),
        DENY_SYSCALL(__NR_umount2),
        DENY_SYSCALL(__NR_pivot_root),
        DENY_SYSCALL(__NR_setns),
        DENY_SYSCALL(__NR_unshare),
        DENY_SYSCALL(__NR_open_by_handle_at),
        DENY_SYSCALL(__NR_name_to_handle_at),
        DENY_SYSCALL(__NR_capset),
        DENY_SYSCALL(__NR_keyctl),
        DENY_SYSCALL(__NR_add_key),
        DENY_SYSCALL(__NR_request_key),
        DENY_SYSCALL(__NR_bpf),
        DENY_SYSCALL(__NR_perf_event_open),
        DENY_SYSCALL(__NR_userfaultfd),
        DENY_SYSCALL(__NR_io_uring_setup),
        DENY_SYSCALL(__NR_io_uring_enter),
        DENY_SYSCALL(__NR_io_uring_register),
        DENY_SYSCALL(__NR_memfd_create),
        DENY_SYSCALL(__NR_reboot),
        DENY_SYSCALL(__NR_kexec_load),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog program = {
        .len = (unsigned short)(sizeof(filter) / sizeof(filter[0])),
        .filter = filter,
    };
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        return -1;
    }
    return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program);
}

static int set_limit(int resource, rlim_t value) {
    struct rlimit limit = {.rlim_cur = value, .rlim_max = value};
    return setrlimit(resource, &limit);
}

static int drop_bounding_set(void) {
    int capability;
    for (capability = 0; capability < 64; capability++) {
        if (prctl(PR_CAPBSET_DROP, capability, 0, 0, 0) != 0
            && errno != EINVAL) {
            return -1;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    uid_t uid;
    gid_t gid;
    int descriptor;
    char env_unbuffered[] = "PYTHONUNBUFFERED=1";
    char env_run[96];
    char env_protocol[128];
    const char *run_id;
    const char *protocol;
    char *clean_env[4];

    if (argc < 6) {
        dprintf(STDERR_FILENO, "launcher: invalid arguments\n");
        return 111;
    }
    uid = (uid_t)strtoul(argv[2], NULL, 10);
    gid = (gid_t)strtoul(argv[3], NULL, 10);
    run_id = getenv("POLICY_RUN_ID");
    protocol = getenv("POLICY_PROTOCOL_VERSION");
    if (run_id == NULL || protocol == NULL) {
        dprintf(STDERR_FILENO, "launcher: missing sanitized environment\n");
        return 112;
    }
    if (snprintf(env_run, sizeof(env_run), "POLICY_RUN_ID=%s", run_id)
        >= (int)sizeof(env_run)
        || snprintf(env_protocol, sizeof(env_protocol),
                    "POLICY_PROTOCOL_VERSION=%s", protocol)
        >= (int)sizeof(env_protocol)) {
        dprintf(STDERR_FILENO, "launcher: environment too long\n");
        return 113;
    }
    clean_env[0] = env_unbuffered;
    clean_env[1] = env_run;
    clean_env[2] = env_protocol;
    clean_env[3] = NULL;

    if (prctl(PR_SET_PDEATHSIG, SIGKILL, 0, 0, 0) != 0
        || chroot(argv[1]) != 0
        || chdir("/policy") != 0
        || drop_bounding_set() != 0
        || setgroups(0, NULL) != 0
        || setgid(gid) != 0
        || setuid(uid) != 0
        || set_limit(RLIMIT_AS, (rlim_t)1024 * 1024 * 1024) != 0
        || set_limit(RLIMIT_CPU, 30) != 0
        || set_limit(RLIMIT_NPROC, 16) != 0
        || set_limit(RLIMIT_NOFILE, 16) != 0
        || set_limit(RLIMIT_FSIZE, (rlim_t)4 * 1024 * 1024) != 0) {
        dprintf(STDERR_FILENO, "launcher: isolation setup failed\n");
        return 114;
    }
    {
        struct rlimit core = {.rlim_cur = 0, .rlim_max = 0};
        if (setrlimit(RLIMIT_CORE, &core) != 0) {
            dprintf(STDERR_FILENO, "launcher: core limit failed\n");
            return 115;
        }
    }
    for (descriptor = 3; descriptor < 1024; descriptor++) {
        close(descriptor);
    }
    if (install_filter() != 0) {
        dprintf(STDERR_FILENO, "launcher: seccomp setup failed\n");
        return 116;
    }
    execve(argv[4], &argv[4], clean_env);
    dprintf(STDERR_FILENO, "launcher: exec failed\n");
    return 117;
}
