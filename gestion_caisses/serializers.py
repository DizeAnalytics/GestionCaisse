from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Region, Prefecture, Commune, Canton, Village,
    Caisse, Membre, Pret, Echeance, MouvementFond, 
    VirementBancaire, AuditLog, Notification, CaisseGenerale, CaisseGeneraleMouvement, RapportActivite
)


class UserSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les utilisateurs Django"""
    role = serializers.SerializerMethodField()
    caisse_nom = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser', 'date_joined', 'last_login', 'role', 'caisse_nom']
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_role(self, obj):
        """Détermine le rôle de l'utilisateur basé sur son profil membre"""
        try:
            membre = obj.profil_membre
            return membre.role
        except:
            if obj.is_superuser:
                return 'ADMIN'
            return 'MEMBRE'
    
    def get_caisse_nom(self, obj):
        """Récupère le nom de la caisse de l'utilisateur"""
        try:
            membre = obj.profil_membre
            return membre.caisse.nom_association if membre.caisse else None
        except:
            return None


class RegionSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les régions"""
    class Meta:
        model = Region
        fields = '__all__'


class PrefectureSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les préfectures"""
    region = RegionSerializer(read_only=True)
    region_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Prefecture
        fields = '__all__'


class CommuneSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les communes"""
    prefecture = PrefectureSerializer(read_only=True)
    prefecture_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Commune
        fields = '__all__'


class CantonSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les cantons"""
    commune = CommuneSerializer(read_only=True)
    commune_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Canton
        fields = '__all__'


class VillageSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les villages"""
    canton = CantonSerializer(read_only=True)
    canton_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Village
        fields = '__all__'


class MembreSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les membres"""
    nom_complet = serializers.ReadOnlyField()
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    caisse_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Membre
        fields = '__all__'
        extra_kwargs = {
            'photo': {'required': False},
            'date_adhesion': {'read_only': True},
            'date_derniere_activite': {'read_only': True},
            'caisse': {'read_only': True},
        }


class CaisseSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les caisses"""
    region = RegionSerializer(read_only=True)
    prefecture = PrefectureSerializer(read_only=True)
    commune = CommuneSerializer(read_only=True)
    canton = CantonSerializer(read_only=True)
    village = VillageSerializer(read_only=True)
    
    # IDs pour la création/modification
    region_id = serializers.IntegerField(write_only=True)
    prefecture_id = serializers.IntegerField(write_only=True)
    commune_id = serializers.IntegerField(write_only=True)
    canton_id = serializers.IntegerField(write_only=True)
    village_id = serializers.IntegerField(write_only=True)
    
    # Champs calculés
    nombre_membres = serializers.ReadOnlyField()
    nombre_prets_actifs = serializers.ReadOnlyField()
    solde_disponible = serializers.ReadOnlyField()
    
    # Membres dirigeants
    presidente = MembreSerializer(read_only=True)
    secretaire = MembreSerializer(read_only=True)
    tresoriere = MembreSerializer(read_only=True)
    
    presidente_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    secretaire_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    tresoriere_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Caisse
        fields = '__all__'
        extra_kwargs = {
            'code': {'read_only': True},
            'date_creation': {'read_only': True},
            'fond_disponible': {'read_only': True},
            'montant_total_prets': {'read_only': True},
            'montant_total_remboursements': {'read_only': True},
        }


class EcheanceSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les échéances"""
    pret_numero = serializers.CharField(source='pret.numero_pret', read_only=True)
    
    class Meta:
        model = Echeance
        fields = '__all__'
        extra_kwargs = {
            'date_paiement': {'required': False},
        }


class PretSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les prêts"""
    membre = MembreSerializer(read_only=True)
    caisse = CaisseSerializer(read_only=True)
    membre_id = serializers.IntegerField(write_only=True)
    caisse_id = serializers.IntegerField(write_only=True)
    
    # Champs calculés
    montant_restant = serializers.ReadOnlyField()
    total_a_rembourser = serializers.ReadOnlyField()
    est_en_retard = serializers.ReadOnlyField()
    
    # Échéances
    echeances = EcheanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Pret
        fields = '__all__'
        extra_kwargs = {
            'numero_pret': {'read_only': True},
            'date_demande': {'read_only': True},
            'date_validation': {'required': False},
            'date_decaissement': {'required': False},
            'date_fin_pret': {'read_only': True},
            'date_remboursement_complet': {'required': False},
            'montant_rembourse': {'read_only': True},
            'nombre_echeances': {'read_only': True},
            'nombre_echeances_payees': {'read_only': True},
        }


class MouvementFondSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les mouvements de fonds"""
    caisse = CaisseSerializer(read_only=True)
    pret = PretSerializer(read_only=True)
    utilisateur = UserSerializer(read_only=True)
    
    caisse_id = serializers.IntegerField(write_only=True)
    pret_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = MouvementFond
        fields = '__all__'
        extra_kwargs = {
            'date_mouvement': {'read_only': True},
            'solde_avant': {'read_only': True},
            'solde_apres': {'read_only': True},
        }


class VirementBancaireSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les virements bancaires"""
    caisse = CaisseSerializer(read_only=True)
    caisse_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = VirementBancaire
        fields = '__all__'
        extra_kwargs = {
            'date_demande': {'read_only': True},
            'date_execution': {'required': False},
            'reference_bancaire': {'required': False},
        }


class CaisseGeneraleSerializer(serializers.ModelSerializer):
    solde_systeme = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = CaisseGenerale
        fields = ['id', 'nom', 'solde_reserve', 'solde_total_caisses', 'solde_systeme', 'actif', 'date_mise_a_jour']


class CaisseGeneraleMouvementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaisseGeneraleMouvement
        fields = '__all__'


class RapportActiviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapportActivite
        fields = '__all__'


class AuditLogSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()
    
    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ['date_action']


class NotificationSerializer(serializers.ModelSerializer):
    destinataire = serializers.StringRelatedField()
    caisse = serializers.StringRelatedField()
    pret = serializers.StringRelatedField()
    
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['date_creation']


class NotificationListSerializer(serializers.ModelSerializer):
    destinataire = serializers.StringRelatedField()
    caisse = serializers.StringRelatedField()
    pret = serializers.StringRelatedField()
    pret_id = serializers.IntegerField(source='pret.id', read_only=True)
    pret_statut = serializers.CharField(source='pret.statut', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'destinataire', 'type_notification', 'titre', 'message', 'caisse', 'pret', 'pret_id', 'pret_statut',
            'statut', 'date_creation', 'lien_action'
        ]
        read_only_fields = ['date_creation']


# Sérialiseurs pour les listes et détails
class CaisseListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des caisses"""
    region_nom = serializers.CharField(source='region.nom', read_only=True)
    prefecture_nom = serializers.CharField(source='prefecture.nom', read_only=True)
    commune_nom = serializers.CharField(source='commune.nom', read_only=True)
    nombre_membres = serializers.ReadOnlyField()
    solde_disponible = serializers.ReadOnlyField()
    
    class Meta:
        model = Caisse
        fields = [
            'id', 'code', 'nom_association', 'region_nom', 'prefecture_nom', 
            'commune_nom', 'statut', 'nombre_membres', 'fond_disponible', 
            'solde_disponible', 'date_creation'
        ]


class MembreListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des membres"""
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    nom_complet = serializers.ReadOnlyField()
    photo = serializers.ImageField(read_only=True)
    numero_telephone = serializers.CharField(read_only=True)
    
    class Meta:
        model = Membre
        fields = [
            'id', 'numero_carte_electeur', 'nom_complet', 'role', 'statut',
            'caisse_nom', 'date_adhesion', 'numero_telephone', 'photo'
        ]


class PretListSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour la liste des prêts"""
    membre_nom = serializers.CharField(source='membre.nom_complet', read_only=True)
    caisse_nom = serializers.CharField(source='caisse.nom_association', read_only=True)
    montant_restant = serializers.ReadOnlyField()
    total_a_rembourser = serializers.ReadOnlyField()
    taux_interet = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    
    class Meta:
        model = Pret
        fields = [
            'id', 'numero_pret', 'membre_nom', 'caisse_nom', 'montant_demande',
            'montant_accord', 'statut', 'date_demande', 'montant_restant',
            'total_a_rembourser', 'taux_interet'
        ]


# Sérialiseurs pour les statistiques et tableaux de bord
class CaisseStatsSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les statistiques des caisses"""
    nombre_membres = serializers.ReadOnlyField()
    nombre_prets_actifs = serializers.ReadOnlyField()
    montant_total_prets = serializers.ReadOnlyField()
    montant_total_remboursements = serializers.ReadOnlyField()
    solde_disponible = serializers.ReadOnlyField()
    
    class Meta:
        model = Caisse
        fields = [
            'id', 'code', 'nom_association', 'statut', 'nombre_membres',
            'nombre_prets_actifs', 'fond_disponible', 'montant_total_prets',
            'montant_total_remboursements', 'solde_disponible'
        ]


class DashboardStatsSerializer(serializers.Serializer):
    total_caisses = serializers.IntegerField()
    total_membres = serializers.IntegerField()
    total_prets_actifs = serializers.IntegerField()
    montant_total_circulation = serializers.DecimalField(max_digits=15, decimal_places=2)
    solde_total_disponible = serializers.DecimalField(max_digits=15, decimal_places=2)
    caisses_par_region = serializers.ListField()
    evolution_prets = serializers.ListField()
    taux_remboursement = serializers.FloatField()
    notifications_non_lues = serializers.IntegerField()
    demandes_pret_en_attente = serializers.IntegerField()
