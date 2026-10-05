/* Observe the constructor of message 0x20005 without changing its payload or
 * delivery. The guarded constructor takes only RCX=this, RDX=payload; it sets
 * R8/R9 itself before its first call and reads no incoming vector arguments.
 * Replay its RBX home store, retain both inputs across the logger, then resume
 * its original body. At most 16 scalar records per image; no URLs or tickets.
 */
.intel_syntax noprefix
.text
.global sc_ui_close
sc_ui_close:
    mov qword ptr [rsp+0x10], rbx
    push rcx
    push rdx
    sub rsp, 0x38                 /* aligned Win64 call, shadow + one vararg */
    cmp dword ptr [rip+close_count], 16
    jae done
    mov eax, 1
    lock xadd dword ptr [rip+close_count], eax
    cmp eax, 16
    jae done
    mov r8d, dword ptr [rdx]       /* the original four-byte payload */
    mov r9, rdx                   /* which object's field supplied it */
    mov rax, qword ptr [rsp+0x48]  /* original constructor caller */
    mov qword ptr [rsp+0x20], rax
    lea rdx, [rip+message]
    xor ecx, ecx
    call helper_log
done:
    add rsp, 0x38
    pop rdx
    pop rcx
    jmp ctor_continue
message:
    .asciz "[sc-ui] msg20005 value=%u source=%p caller=%p"
