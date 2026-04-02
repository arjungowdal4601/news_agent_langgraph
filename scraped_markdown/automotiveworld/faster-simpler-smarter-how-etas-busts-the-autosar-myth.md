---
title: Faster, simpler, smarter: how ETAS busts the AUTOSAR myth | Automotive World
author: Megan Lampinen
url: https://www.automotiveworld.com/topics/software-defined-vehicle/faster-simpler-smarter-how-etas-busts-the-autosar-myth/
hostname: automotiveworld.com
description: ETAS offers a deep dive into how RTA-CAR tackles the main pain points in AUTOSAR Classic. By Megan Lampinen
sitename: Automotive World
date: 2026-04-02
categories: ['Partner Content', 'Software-Defined Vehicle']
---
AUTOSAR Classic has a reputation for adding complexity and slowing development, but much of that stems from misconception as opposed to fact. Darren Buttle, Chief Product Manager, Embedded Platform Software, at ETAS, argues that the standardised software framework does indeed have a key role to play for teams working on deeply embedded Electronic Control Units (ECUs) in vehicles. The key is ETAS’s RTA-CAR platform, which addresses the real pain points of AUTOSAR development. From streamlining configuration and accelerating code generation to supporting virtualisation and CI/CD workflows, RTA-CAR allows engineering teams to move faster without compromising on safety, security, or footprint efficiency.

**Where does AUTOSAR’s reputation for complexity come from, and is it justified?**

AUTOSAR’s complexity is essentially a consequence of how it was built. Over 25 years, contributors brought their own ideas to the table, and the standard grew by aggregating all of them. Everyone could find their particular solution inside it and ignore the rest. The goal was more about coverage than simplicity—how do we accommodate as many variations and corner cases as possible? Also, much of AUTOSAR was built to support the migration of legacy solutions from the pre-AUTOSAR era, and to reflect the way OEMs approach systems engineering.

**When you strip away the misconceptions, what is AUTOSAR Classic trying to solve?**

At its core, AUTOSAR is trying to solve the fundamental challenges of deeply embedded real-time systems: runtime scheduling, reliable communication, reliable data storage, and the ability to diagnose systems in the field. An AUTOSAR system runs on bare metal; there is nothing else on the device until you put the stack on it. AUTOSAR essentially provides the glue between the hardware, which varies significantly from chip to chip, and the OEM requirements, which have a similar variance.

![](https://media.automotiveworld.com/app/uploads/2026/03/31122140/Middleware_Visual_RTA-CAR_Verlauf_16_9.jpg)


**Much of the frustration with AUTOSAR seems to centre on implementation rather than the standard itself. How does poor tooling or workflow integration turn a sound framework into a development bottleneck?**

The frustration is less about the implementation and more about the configuration. The configuration space contains hundreds of thousands of elements, and there’s a genuine paradox of choice at work. When you come into AUTOSAR with a specific engineering problem, you’re confronted with an enormous array of options, but the standard itself offers very little guidance on which ones are appropriate for a given situation. The result is a semantic gap between the problem you’re trying to solve and what AUTOSAR tells you is possible. That gap is where a lot of time and risk accumulate.

**How does the ETAS platform specifically address those implementation pain points? **

We’re primarily selling two things: the first of which is time. When a customer asks whether we have a tool for something, they’re really asking whether this makes their job faster. We want to shorten the time between having an idea and having something you can test on an ECU, between making a change and seeing the impact of that change. That directly correlates to the engineer’s efficiency. Instead of waiting eight hours for something to build, RTA-CAR can turn it around in a handful of minutes. That means you can look at 20, 30, maybe 50 changes a day rather than just one.

The second thing we’re selling is expertise, the insights and experience we’ve accumulated over decades. Our tooling doesn’t offer just automation, but automation that reflects deep knowledge of the problem space, allowing customers to move not just faster, but faster in the right direction.

**Deeply embedded software development carries unique constraints: determinism, memory footprint, safety certification. How does your approach handle those without forcing engineers to trade off one against another?**

The classic trade-off is between space and time: things that are faster generally take more space, while things that are slower take less space. We have some nice optimisations in the operating system kernel that allow you to get much better control on that space/time trade-off. For instance, the ability to trade off slack time in the system for reduced RAM footprint, or vice versa, gives developers more flexible control over system resources.

We also leverage the fact that we were very much a code generation first solution, rather than writing a set of standard code, and then generating some data on which the code operates. We want to generate the least amount of code and data needed to make the customer’s configuration come to life. That results in solutions that are three to four times smaller than competing solutions.

**How does RTA-CAR specifically simplify configuration, reduce integration time, and make debugging less of a headache? **

With RTA-CAR’s import capabilities and automatic configuration workflows, you can take a set of OEM files and arrive at a near-working ECU remarkably quickly. Our starter kits are ready-made reference integrations with a very basic skeleton system setup, for a particular device with a particular set of third-party microcontroller obstruction software. The idea is to get up and running as fast as possible. The virtual ECU really speeds up integration. Running integration on your host PC rather than on the chip itself delivers dramatically faster turnaround. Compilation is quicker, debugging is simpler, and you’re not constrained by the limitations of embedded hardware. Issues will inevitably emerge when you move to embedded hardware, but having already validated your software in a virtual environment, you know that any new failures are confined to the hardware-software interface, not broader software defects. The virtual ECU approach lets you front-load the majority of your debugging effort. By the time you reach the target hardware, you’re dealing with a much smaller, well-defined set of remaining challenges.

![](https://media.automotiveworld.com/app/uploads/2026/03/31122241/rta-car-composition-editor-editor-laptop-graphic-en-etas-241022_res_1600x900.webp)

**From your experience working with OEMs and Tier 1 suppliers, where do development teams typically lose the most time or introduce the most risk when working with deeply embedded software, and what does fixing that look like?**

When you’re tooling up to use a new piece of silicon, there will always be bugs in the device at some point. It really helps if you can work on virtual silicon before it goes into fabrication. The complexity of the chips themselves makes things massively more complicated now. A job to tool a single core microcontroller used to be two or three days; now it can take months just trying to get the chip to boot reliably.

The other common challenges are around the use of resources on the device. If you have a big multicore system on a chip, you have a lot of parallel processing that introduces new challenges. With two bits of functionality that need to somehow exchange some data, sooner or later, one of them has to stop executing, transfer a piece of data, wait for something to happen, and receive the data back. We have things in our tooling to help teams understand exactly what data is going backwards and forwards between cores, and the best way of making sure you force serialisation and mutual exclusion of those pieces of data to avoid things like data corruption.

There are also aspects here to do with overall performance. A CPU core might have core local memory as well as memory shared with other CPUs. A different CPU might have its own core local memory. All of those memories have different access times. Where data gets placed in the system has a significant impact on the overall timing responsiveness. We can help customers understand the relevant costs and compromises around data placement and access.

**If an engineering team is starting a new deeply embedded software programme today, what would you want them to understand about how the right platform choice at the outset shapes what’s possible—and what isn’t—two or three years down the line?**

They need to identify the problem they want to solve in the simplest possible way. Then our field engineering teams can help them work out the right constellation to get the job done. Understanding the complexity of the application that needs to be run is probably one of the most fundamental things in any project.

**If you could give one piece of advice to a development team, or a manager who is hesitant to embrace an AUTOSAR Classic-based workflow, what would it be? **

There’s a wealth of embedded engineering experience in AUTOSAR that provides elegant solutions to real-world engineering problems, and you need an experienced partner like ETAS to guide you to the treasure and help you leverage this beauty in your project.