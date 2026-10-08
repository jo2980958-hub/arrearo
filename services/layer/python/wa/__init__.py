"""Arrearo's WhatsApp-native app layer: login, session, navigation, views, actions.

See the design spec: docs/superpowers/specs/2026-10-08-arrearo-whatsapp-app-design.md.
Each module is small and unit-tested with stubbed boto3. The webhook routes inbound
WhatsApp through wa.router.handle().
"""
