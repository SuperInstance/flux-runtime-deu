"""
FLUX-deu KasusCapabilityChecker — Kasus-basierte Capability-Erzwingung.

German cases map directly to capability-based access control at the opcode level:

    Nominativ  → CAP_READ:   can observe but not modify
    Akkusativ  → CAP_WRITE:  can modify the accusative object
    Dativ      → CAP_DELEGATE: can pass capabilities via the dative object
    Genitiv    → CAP_OWN:   has ownership, can transfer

Capability Escalation:
    Dativ + Genitiv together → can delegate ownership (like sudo)
    Nominativ + Akkusativ → can read and write (basic access)
    All four → CAP_ROOT: full system access

Usage:
    checker = KasusCapabilityChecker()
    checker.define_register("R0", Kasus.AKKUSATIV)
    checker.check_opcode("R0", CapLevel.CAP_WRITE)   # True
    checker.check_opcode("R0", CapLevel.CAP_OWN)     # False
    checker.check_opcode("R0", CapLevel.CAP_READ)     # True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Dict, List, Optional, Tuple

from flux_deu.kasus import (
    Kasus, CapLevel, KasusValidator, KasusScope, KASUS_TO_CAP, CAP_TO_KASUS,
)


# ══════════════════════════════════════════════════════════════════════
# Extended Capability Levels (beyond basic Kasus)
# ══════════════════════════════════════════════════════════════════════

class ExtendedCap(IntEnum):
    """
    扩展的 Capability 级别 — 基于 Kasus 组合。

    基础 (来自 Kasus):
        CAP_PUBLIC    = 0   (Nominativ)
        CAP_REFERENCE = 1   (Dativ)
        CAP_READWRITE = 2   (Akkusativ)
        CAP_TRANSFER  = 3   (Genitiv)

    扩展 (Kasus 组合):
        CAP_DELEGATE = 4   (Dativ + Genitiv → sudo-like)
        CAP_FULL      = 5   (all four → root access)
    """
    # 基础 (与 CapLevel 兼容)
    CAP_PUBLIC    = 0
    CAP_REFERENCE = 1
    CAP_READWRITE = 2
    CAP_TRANSFER  = 3

    # 扩展
    CAP_DELEGATE = 4      # Dativ + Genitiv 组合 → 委托所有权
    CAP_FULL      = 5      # 四格俱全 → 完全访问


# Kasus 组合 → 扩展 Capability
KASUS_COMBINATION_CAP: Dict[frozenset, ExtendedCap] = {
    frozenset({Kasus.DATIV}): ExtendedCap.CAP_DELEGATE,
    frozenset({Kasus.DATIV, Kasus.GENITIV}): ExtendedCap.CAP_DELEGATE,
    frozenset({Kasus.NOMINATIV, Kasus.AKKUSATIV}): ExtendedCap.CAP_READWRITE,
    frozenset({Kasus.NOMINATIV, Kasus.DATIV, Kasus.GENITIV}): ExtendedCap.CAP_FULL,
    frozenset({Kasus.NOMINATIV, Kasus.AKKUSATIV, Kasus.DATIV, Kasus.GENITIV}): ExtendedCap.CAP_FULL,
}

# 单个 Kasus → 扩展 Capability (也映射)
KASUS_TO_EXTENDED_CAP: Dict[Kasus, ExtendedCap] = {
    Kasus.NOMINATIV: ExtendedCap.CAP_PUBLIC,
    Kasus.AKKUSATIV: ExtendedCap.CAP_READWRITE,
    Kasus.DATIV: ExtendedCap.CAP_REFERENCE,
    Kasus.GENITIV: ExtendedCap.CAP_TRANSFER,
}

# 扩展 Capability → 所需的最低 Kasus 组合
CAP_REQUIRED_KASUS: Dict[ExtendedCap, frozenset] = {
    ExtendedCap.CAP_PUBLIC: frozenset({Kasus.NOMINATIV}),
    ExtendedCap.CAP_REFERENCE: frozenset({Kasus.NOMINATIV, Kasus.DATIV}),
    ExtendedCap.CAP_READWRITE: frozenset({Kasus.NOMINATIV, Kasus.AKKUSATIV}),
    ExtendedCap.CAP_TRANSFER: frozenset({Kasus.NOMINATIV, Kasus.AKKUSATIV, Kasus.GENITIV}),
    ExtendedCap.CAP_DELEGATE: frozenset({Kasus.NOMINATIV, Kasus.DATIV, Kasus.GENITIV}),
    ExtendedCap.CAP_FULL: frozenset({Kasus.NOMINATIV, Kasus.AKKUSATIV, Kasus.DATIV, Kasus.GENITIV}),
}


# ══════════════════════════════════════════════════════════════════════
# Opcode → 所需 Capability 级别
# ══════════════════════════════════════════════════════════════════════

class OpcodeRequirement:
    """操作码所需的 Capability 级别"""
    NOP = ExtendedCap.CAP_PUBLIC
    MOV = ExtendedCap.CAP_PUBLIC
    LOAD = ExtendedCap.CAP_PUBLIC
    STORE = ExtendedCap.CAP_READWRITE
    JMP = ExtendedCap.CAP_PUBLIC
    JZ = ExtendedCap.CAP_PUBLIC
    JNZ = ExtendedCap.CAP_PUBLIC
    CALL = ExtendedCap.CAP_DELEGATE
    IADD = ExtendedCap.CAP_READWRITE
    ISUB = ExtendedCap.CAP_READWRITE
    IMUL = ExtendedCap.CAP_READWRITE
    IDIV = ExtendedCap.CAP_READWRITE
    IMOD = ExtendedCap.CAP_READWRITE
    INEG = ExtendedCap.CAP_READWRITE
    INC = ExtendedCap.CAP_READWRITE
    DEC = ExtendedCap.CAP_READWRITE
    CMP = ExtendedCap.CAP_PUBLIC
    PRINT = ExtendedCap.CAP_PUBLIC
    TELL = ExtendedCap.CAP_DELEGATE
    ASK = ExtendedCap.CAP_DELEGATE
    DELEGATE = ExtendedCap.CAP_DELEGATE
    BROADCAST = ExtendedCap.CAP_DELEGATE
    TRUST_CHECK = ExtendedCap.CAP_DELEGATE
    CAP_REQUIRE = ExtendedCap.CAP_DELEGATE
    REGION_CREATE = ExtendedCap.CAP_DELEGATE
    REGION_TRANSFER = ExtendedCap.CAP_TRANSFER
    REGION_DESTROY = ExtendedCap.CAP_TRANSFER
    HALT = ExtendedCap.CAP_PUBLIC
    RET = ExtendedCap.CAP_PUBLIC
    # All other opcodes default to CAP_PUBLIC
    CAST = ExtendedCap.CAP_READWRITE
    BOX = ExtendedCap.CAP_READWRITE
    UNBOX = ExtendedCap.CAP_READWRITE
    CHECK_TYPE = ExtendedCap.CAP_PUBLIC
    CHECK_BOUNDS = ExtendedCap.CAP_PUBLIC
    PUSH = ExtendedCap.CAP_PUBLIC
    POP = ExtendedCap.CAP_PUBLIC


# ══════════════════════════════════════════════════════════════════════
# Capability Violation Exception
# ══════════════════════════════════════════════════════════════════════

@dataclass
class CapabilityViolation:
    """Capability 违规记录"""
    register: int
    register_kasus: Kasus
    required_cap: ExtendedCap
    available_cap: ExtendedCap
    opcode_name: str
    description: str

    @property
    def kasus_name(self) -> str:
        return self.register_kasus.value

    @property
    def required_name(self) -> str:
        return self.required_cap.name

    @property
    def available_name(self) -> str:
        return self.available_cap.name

    def __repr__(self) -> str:
        return (
            f"CapViolation(R{self.register} [{self.kasus_name}], "
            f"need={self.required_name}, have={self.available_name}, "
            f"op={self.opcode_name}: {self.description})"
        )


# ══════════════════════════════════════════════════════════════════════
# KasusCapabilityChecker — 核心检查器
# ════════════════════════════════════════════════════════════════════

class KasusCapabilityChecker:
    """
    Kasus-basierte Capability-Prüfung für Opcode-Ausführung.

    在每条指令执行前检查当前 Kasus 是否授予所需的 Capability 级别。

    使用方法:
        checker = KasusCapabilityChecker()
        checker.define_register("R0", Kasus.AKKUSATIV)
        checker.define_register("R1", Kasus.GENITIV)

        # 检查单个寄存器的 capability
        checker.check_register("R0", ExtendedCap.CAP_WRITE)  # True
        checker.check_register("R0", ExtendedCap.CAP_OWN)   # False

        # 检查 opcode 执行所需的所有寄存器
        checker.check_opcode("R0", "R1", OpcodeRequirement.STORE)  # True

        # 能力升级: R60 + R62 (Dativ + Genitiv) = CAP_DELEGATE
        checker.define_register("R60", Kasus.DATIV)
        checker.define_register("R62", Kasus.GENITIV)
        checker.collective_kasus()  # → CAP_DELEGATE (sudo-like)
    """

    def __init__(self, strict: bool = True):
        """
        Args:
            strict: 如果为 True, 违规时抛出异常; 否则只记录
        """
        self.strict = strict
        self._register_kasus: Dict[int, Kasus] = {
            i: Kasus.NOMINATIV for i in range(64)
        }
        # R60-R63 特殊 Kasus 初始化
        self._register_kasus[60] = Kasus.NOMINATIV  # 主题
        self._register_kasus[61] = Kasus.NOMINATIV  # 对象
        self._register_kasus[62] = Kasus.DATIV      # Dativ
        self._register_kasus[63] = Kasus.GENITIV    # Genitiv

        self._violation_log: List[CapabilityViolation] = []
        self._access_count = 0
        self._deny_count = 0

    def define_register(self, register: str | int, kasus: Kasus) -> None:
        """
        定义寄存器的 Kasus.

        Args:
            register: 寄存器名 ("R0" or 0)
            kasus: Kasus 枚举值
        """
        reg_num = self._parse_register(register)
        self._register_kasus[reg_num] = kasus

    def get_register_kasus(self, register: str | int) -> Kasus:
        """获取寄存器的当前 Kasus"""
        reg_num = self._parse_register(register)
        return self._register_kasus.get(reg_num, Kasus.NOMINATIV)

    def get_extended_cap(self, register: str | int) -> ExtendedCap:
        """获取寄存器的扩展 Capability 级别"""
        reg_num = self._parse_register(register)
        return KASUS_TO_EXTENDED_CAP[self._register_kasus[reg_num]]

    def get_collective_kasus(self) -> ExtendedCap:
        """
        获取当前所有已定义寄存器的集合 Kasus Capability。

        组合所有寄存器的 Kasus, 取最大能力。

        Returns:
            集合 Kasus Capability
        """
        active_kasus: set = set()
        for reg_num, kasus in self._register_kasus.items():
            # Nominativ is always implied
            active_kasus.add(Kasus.NOMINATIV)
            active_kasus.add(kasus)

        # 检查各级别
        if active_kasus >= CAP_REQUIRED_KASUS[ExtendedCap.CAP_FULL]:
            return ExtendedCap.CAP_FULL
        if active_kasus >= CAP_REQUIRED_KASUS[ExtendedCap.CAP_DELEGATE]:
            return ExtendedCap.CAP_DELEGATE
        if active_kasus >= CAP_REQUIRED_KASUS[ExtendedCap.CAP_TRANSFER]:
            return ExtendedCap.CAP_TRANSFER
        if active_kasus >= CAP_REQUIRED_KASUS[ExtendedCap.CAP_READWRITE]:
            return ExtendedCap.CAP_READWRITE
        if active_kasus >= CAP_REQUIRED_KASUS[ExtendedCap.CAP_REFERENCE]:
            return ExtendedCap.CAP_REFERENCE
        return ExtendedCap.CAP_PUBLIC

    @property
    def collective_kasus_name(self) -> str:
        """集合 Kasus 的中文名"""
        cap = self.get_collective_kasus()
        return cap.name

    def check_register(self, register: str | int, required: ExtendedCap) -> bool:
        """
        检查单个寄存器是否满足所需的 Capability。

        Args:
            register: 寄存器
            required: 所需的 Capability 级别

        Returns:
            True 如果满足, False 否则
        """
        self._access_count += 1
        reg_num = self._parse_register(register)
        available = self.get_extended_cap(reg_num)
        satisfied = available >= required

        if not satisfied:
            self._deny_count += 1
            violation = CapabilityViolation(
                register=reg_num,
                register_kasus=self._register_kasus[reg_num],
                required_cap=required,
                available_cap=available,
                opcode_name="(register check)",
                description=(
                    f"R{reg_num} hat {available.name} "
                    f"({self._register_kasus[reg_num].value}), "
                    f"benötigt {required.name}"
                ),
            )
            self._violation_log.append(violation)
            if self.strict:
                raise PermissionError(
                    f"Capability-Verletzung: {violation.description}"
                )

        return satisfied

    def check_opcode(self, *registers: str | int,
                     opcode_req: ExtendedCap | None = None) -> bool:
        """
        检查 opcode 执行所需的所有寄存器 capability。

        Args:
            registers: 操作码涉及的所有寄存器
            opcode_req: 操作码本身所需的 capability (默认 CAP_PUBLIC)

        Returns:
            True 如果所有寄存器满足 capability, False 否则
        """
        if opcode_req is None:
            opcode_req = OpcodeRequirement.NOP

        # 所有涉及的寄存器都必须满足操作码需求
        for reg in registers:
            if not self.check_register(reg, opcode_req):
                return False
        return True

    def check_store(self, source: str | int, target: str | int) -> bool:
        """
        检查存储操作 (STORE) — 源需要 READWRITE, 目标需要 READWRITE.

        Args:
            source: 源寄存器
            target: 目标寄存器

        Returns:
            True 如果双方都满足
        """
        return (
            self.check_register(source, ExtendedCap.CAP_READWRITE)
            and self.check_register(target, ExtendedCap.CAP_READWRITE)
        )

    def check_load(self, source: str | int) -> bool:
        """检查加载操作 — 源需要 PUBLIC (Nominativ) 即可读取"""
        return self.check_register(source, ExtendedCap.CAP_PUBLIC)

    def check_transfer(self, source: str | int, target: str | int) -> bool:
        """
        检查所有权转移 — 源需要 TRANSFER (Genitiv), 目标需要 READWRITE。

        用法: REGION_TRANSFER, DELEGATE 等操作
        """
        return (
            self.check_register(source, ExtendedCap.CAP_TRANSFER)
            and self.check_register(target, ExtendedCap.CAP_READWRITE)
        )

    def check_delegate(self, agent: str | int, task: str | int) -> bool:
        """
        检查委托操作 — 需要 DELEGATE (Dativ + Genitiv 组合)。

        用法: DELEGATE opcode
        """
        return (
            self.check_register(agent, ExtendedCap.CAP_DELEGATE)
            or self.check_register(task, ExtendedCap.CAP_DELEGATE)
        )

    def check_broadcast(self, register: str | int) -> bool:
        """
        检查广播操作 — 需要 DELEGATE (可以广播 = 可以委托)

        用法: BROADCAST opcode
        """
        return self.check_register(register, ExtendedCap.CAP_DELEGATE)

    def check_trust(self, register: str | int) -> bool:
        """
        检查信任验证 — 需要 DELEGATE

        用法: TRUST_CHECK opcode
        """
        return self.check_register(register, ExtendedCap.CAP_DELEGATE)

    @property
    def violation_log(self) -> List[CapabilityViolation]:
        """获取所有违规记录"""
        return list(self._violation_log)

    @property
    def access_count(self) -> int:
        """总检查次数"""
        return self._access_count

    @property
    def deny_count(self) -> int:
        """被拒绝的检查次数"""
        return self._deny_count

    @property
    def allow_count(self) -> int:
        """通过的检查次数"""
        return self._access_count - self._deny_count

    @property
    def deny_rate(self) -> float:
        """拒绝率"""
        if self._access_count == 0:
            return 0.0
        return self._deny_count / self._access_count

    def reset(self) -> None:
        """重置所有寄存器为 Nominativ"""
        self._register_kasus = {i: Kasus.NOMINATIV for i in range(64)}
        self._register_kasus[62] = Kasus.DATIV
        self._register_kasus[63] = Kasus.GENITIV
        self._violation_log.clear()
        self._access_count = 0
        self._deny_count = 0

    def summary(self) -> str:
        """生成 Capability 检查摘要"""
        lines = [
            "Kasus Capability-Prüfung:",
            f"  Prüfungen: {self._access_count}",
            f"  Erlaubt: {self.allow_count}",
            f"  Abgelehnt: {self._deny_count}",
            f"  Ablehnungsrate: {self.deny_rate:.1%}" if self._access_count > 0 else "  (keine Prüfungen)",
        ]

        # 特殊寄存器状态
        specials = [
            (60, "主题 (Nominativ)"),
            (61, "Objekt (Nominativ)"),
            (62, "Dativ-Referenz"),
            (63, "Genitiv-Besitz"),
        ]
        for reg_num, desc in specials:
            kasus = self._register_kasus[reg_num]
            cap = self.get_extended_cap(reg_num)
            lines.append(f"  R{reg_num:02d} {desc}: {kasus.value} → {cap.name}")

        # 最近违规
        if self._violation_log:
            lines.append(f"  Letzte {len(self._violation_log)} Verletzungen:")
            for v in self._violation_log[-5:]:
                lines.append(f"    {v}")

        return "\n".join(lines)

    def _parse_register(self, register: str | int) -> int:
        """解析寄存器名"""
        if isinstance(register, int):
            return register
        s = register.strip().upper()
        if s.startswith("R"):
            try:
                num = int(s[1:])
                if 0 <= num < 64:
                    return num
            except ValueError:
                pass
        return 0

    def __repr__(self) -> str:
        return (
            f"KasusCapabilityChecker("
            f"accesses={self._access_count}, "
            f"denied={self._deny_count}, "
            f"strict={self.strict})"
        )
