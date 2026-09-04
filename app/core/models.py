from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class AccessEvaluationResult:
    """
    Result of a Linux kernel DAC (Discretionary Access Control) evaluation.
    Explains the 3-step kernel decision algorithm based on real POSIX metadata.
    """
    matched_class: str  # "owner", "group", "other"
    step_number: int  # 1 (Owner check), 2 (Group check), 3 (Other check)
    decision_reason: str
    can_read: bool
    can_write: bool
    can_execute: bool
    read_reason: str
    write_reason: str
    execute_reason: str


@dataclass
class FilesystemObject:
    """
    Domain model representing a Linux filesystem entry and its POSIX metadata.
    Decouples raw Linux OS stat inspection from UI visualizers.
    """
    path: Path
    name: str
    parent: Path
    file_type: str
    is_dir: bool
    is_file: bool
    is_symlink: bool
    is_broken_symlink: bool
    symlink_target: str | None

    # Inode & Storage
    inode_number: int
    device_id: int
    hard_link_count: int
    size_bytes: int
    allocated_blocks_512b: int
    filesystem_block_size: int

    # Ownership
    uid: int
    owner_name: str
    gid: int
    group_name: str

    # Permissions & Modes
    mode: int
    permission_mode: int  # 12 bits (includes SUID/SGID/Sticky)
    standard_mode: int    # 9 bits (rwxrwxrwx)
    octal_mode: str
    symbolic_mode: str

    # Special Mode Bits
    suid: bool
    sgid: bool
    sticky: bool

    # Permission Matrix
    owner_r: bool
    owner_w: bool
    owner_x: bool
    group_r: bool
    group_w: bool
    group_x: bool
    other_r: bool
    other_w: bool
    other_x: bool

    # Timestamps
    atime: datetime
    mtime: datetime
    ctime: datetime

    @classmethod
    def from_path(cls, path: Path | str) -> FilesystemObject | None:
        """
        Inspect a filesystem path using lstat and build a complete FilesystemObject domain model.
        Returns None if the path does not exist or cannot be inspected.
        """
        try:
            path_obj = Path(path)
            info = os.lstat(path_obj)
        except (OSError, PermissionError, FileNotFoundError):
            return None

        mode = info.st_mode
        perm_mode = mode & 0o7777
        standard_mode = mode & 0o777

        # ----------------------------------------------------
        # Determine File Type & Symlink Target
        # ----------------------------------------------------
        is_symlink = stat.S_ISLNK(mode)
        is_broken_symlink = False
        symlink_target = None

        if is_symlink:
            try:
                symlink_target = os.readlink(path_obj)
                target_path = path_obj.parent / symlink_target
                if target_path.exists():
                    file_type = f"Symbolic link → {symlink_target}"
                else:
                    is_broken_symlink = True
                    file_type = f"Broken symlink → {symlink_target}"
            except OSError:
                file_type = "Symbolic link"
        elif stat.S_ISDIR(mode):
            file_type = "Directory"
        elif stat.S_ISREG(mode):
            file_type = "Regular file"
        elif stat.S_ISFIFO(mode):
            file_type = "Named pipe (FIFO)"
        elif stat.S_ISSOCK(mode):
            file_type = "Socket"
        elif stat.S_ISCHR(mode):
            file_type = "Character device"
        elif stat.S_ISBLK(mode):
            file_type = "Block device"
        else:
            file_type = "Other"

        # ----------------------------------------------------
        # Special Bits (SUID, SGID, Sticky)
        # ----------------------------------------------------
        suid = bool(perm_mode & 0o4000)
        sgid = bool(perm_mode & 0o2000)
        sticky = bool(perm_mode & 0o1000)

        # ----------------------------------------------------
        # Standard Permission Matrix
        # ----------------------------------------------------
        owner_r = bool(standard_mode & 0o400)
        owner_w = bool(standard_mode & 0o200)
        owner_x = bool(standard_mode & 0o100)

        group_r = bool(standard_mode & 0o040)
        group_w = bool(standard_mode & 0o020)
        group_x = bool(standard_mode & 0o010)

        other_r = bool(standard_mode & 0o004)
        other_w = bool(standard_mode & 0o002)
        other_x = bool(standard_mode & 0o001)

        # ----------------------------------------------------
        # Symbolic Mode Formatter (Handles SUID/SGID/Sticky)
        # ----------------------------------------------------
        symbolic_mode = stat.filemode(mode)

        # ----------------------------------------------------
        # Octal Formatting (4 digits if special bits set, else 3 or 4)
        # ----------------------------------------------------
        octal_mode = oct(perm_mode)[2:].zfill(4)

        # ----------------------------------------------------
        # Owner & Group Names
        # ----------------------------------------------------
        try:
            import pwd
            owner_name = pwd.getpwuid(info.st_uid).pw_name
        except Exception:
            owner_name = str(info.st_uid)

        try:
            import grp
            group_name = grp.getgrgid(info.st_gid).gr_name
        except Exception:
            group_name = str(info.st_gid)

        return cls(
            path=path_obj,
            name=path_obj.name or str(path_obj),
            parent=path_obj.parent,
            file_type=file_type,
            is_dir=stat.S_ISDIR(mode),
            is_file=stat.S_ISREG(mode),
            is_symlink=is_symlink,
            is_broken_symlink=is_broken_symlink,
            symlink_target=symlink_target,
            inode_number=info.st_ino,
            device_id=info.st_dev,
            hard_link_count=info.st_nlink,
            size_bytes=info.st_size,
            allocated_blocks_512b=getattr(info, "st_blocks", 0),
            filesystem_block_size=getattr(info, "st_blksize", 4096),
            uid=info.st_uid,
            owner_name=owner_name,
            gid=info.st_gid,
            group_name=group_name,
            mode=mode,
            permission_mode=perm_mode,
            standard_mode=standard_mode,
            octal_mode=octal_mode,
            symbolic_mode=symbolic_mode,
            suid=suid,
            sgid=sgid,
            sticky=sticky,
            owner_r=owner_r,
            owner_w=owner_w,
            owner_x=owner_x,
            group_r=group_r,
            group_w=group_w,
            group_x=group_x,
            other_r=other_r,
            other_w=other_w,
            other_x=other_x,
            atime=datetime.fromtimestamp(info.st_atime),
            mtime=datetime.fromtimestamp(info.st_mtime),
            ctime=datetime.fromtimestamp(info.st_ctime),
        )

    def evaluate_access(
        self,
        subject_uid: int,
        subject_gid: int,
        subject_supplementary_gids: list[int] | set[int] | None = None,
    ) -> AccessEvaluationResult:
        """
        Explains how the Linux Kernel 3-step DAC algorithm evaluates permissions
        for a given Subject (UID, GID, supplementary GIDs) against this object's real POSIX mode.

        Step 1: Check if Subject UID matches File UID (Owner Class).
                If matched, the kernel evaluates ONLY the owner rwx bits and STOPS.
        Step 2: Check if Subject GID or any supplementary group matches File GID (Group Class).
                If matched, the kernel evaluates ONLY the group rwx bits and STOPS.
        Step 3: If neither UID nor GID matches, the kernel evaluates the Other rwx bits.
        """
        if subject_supplementary_gids is None:
            subject_supplementary_gids = set()
        else:
            subject_supplementary_gids = set(subject_supplementary_gids)

        all_subject_gids = {subject_gid} | subject_supplementary_gids
        is_root = (subject_uid == 0)

        # ----------------------------------------------------
        # Step 1: Owner Match Check
        # ----------------------------------------------------
        if subject_uid == self.uid:
            can_read = self.owner_r or is_root
            can_write = self.owner_w or is_root
            can_execute = self.owner_x or (is_root and (self.owner_x or self.group_x or self.other_x))

            return AccessEvaluationResult(
                matched_class="owner",
                step_number=1,
                decision_reason=(
                    f"Step 1 Match: Subject UID ({subject_uid}) matches File Owner UID ({self.uid}). "
                    "Kernel enforces Owner permissions and ignores Group and Other bits."
                ),
                can_read=can_read,
                can_write=can_write,
                can_execute=can_execute,
                read_reason="Allowed by Owner 'r' bit (400)" if self.owner_r else ("Allowed for Root (UID 0)" if is_root else "Denied: Owner 'r' bit is not set"),
                write_reason="Allowed by Owner 'w' bit (200)" if self.owner_w else ("Allowed for Root (UID 0)" if is_root else "Denied: Owner 'w' bit is not set"),
                execute_reason="Allowed by Owner 'x' bit (100)" if self.owner_x else ("Allowed for Root (executable bit present on file)" if can_execute else "Denied: Owner 'x' bit is not set"),
            )

        # ----------------------------------------------------
        # Step 2: Group Match Check
        # ----------------------------------------------------
        if self.gid in all_subject_gids:
            can_read = self.group_r or is_root
            can_write = self.group_w or is_root
            can_execute = self.group_x or (is_root and (self.owner_x or self.group_x or self.other_x))

            matching_type = "Primary GID" if self.gid == subject_gid else "Supplementary Group"

            return AccessEvaluationResult(
                matched_class="group",
                step_number=2,
                decision_reason=(
                    f"Step 2 Match: Subject belongs to File GID ({self.gid}) via {matching_type}. "
                    "Kernel enforces Group permissions and ignores Other bits."
                ),
                can_read=can_read,
                can_write=can_write,
                can_execute=can_execute,
                read_reason="Allowed by Group 'r' bit (040)" if self.group_r else ("Allowed for Root (UID 0)" if is_root else "Denied: Group 'r' bit is not set"),
                write_reason="Allowed by Group 'w' bit (020)" if self.group_w else ("Allowed for Root (UID 0)" if is_root else "Denied: Group 'w' bit is not set"),
                execute_reason="Allowed by Group 'x' bit (010)" if self.group_x else ("Allowed for Root (executable bit present on file)" if can_execute else "Denied: Group 'x' bit is not set"),
            )

        # ----------------------------------------------------
        # Step 3: Other Fallback
        # ----------------------------------------------------
        can_read = self.other_r or is_root
        can_write = self.other_w or is_root
        can_execute = self.other_x or (is_root and (self.owner_x or self.group_x or self.other_x))

        return AccessEvaluationResult(
            matched_class="other",
            step_number=3,
            decision_reason=(
                f"Step 3 Fallback: Subject UID ({subject_uid}) does not match Owner ({self.uid}), "
                f"and Subject groups {sorted(all_subject_gids)} do not match File GID ({self.gid}). "
                "Kernel enforces 'Other / World' permissions."
            ),
            can_read=can_read,
            can_write=can_write,
            can_execute=can_execute,
            read_reason="Allowed by Other 'r' bit (004)" if self.other_r else ("Allowed for Root (UID 0)" if is_root else "Denied: Other 'r' bit is not set"),
            write_reason="Allowed by Other 'w' bit (002)" if self.other_w else ("Allowed for Root (UID 0)" if is_root else "Denied: Other 'w' bit is not set"),
            execute_reason="Allowed by Other 'x' bit (001)" if self.other_x else ("Allowed for Root (executable bit present on file)" if can_execute else "Denied: Other 'x' bit is not set"),
        )
